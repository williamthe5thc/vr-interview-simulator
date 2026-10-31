#!/usr/bin/env python3
"""
WebSocket Testing Tool

This script tests the WebSocket server functionality of the VR Interview System,
including connection handling, state transitions, and message processing.
"""

import sys
import os
import time
import json
import logging
import argparse
import asyncio
import websockets
import base64
import wave
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("websocket_test")

class WebSocketTester:
    """Tests WebSocket server functionality"""
    
    def __init__(self, server_url="ws://localhost:8765"):
        """Initialize the tester with server URL"""
        self.server_url = server_url
        self.websocket = None
        self.session_id = None
        self.current_state = None
        self.message_history = []
        self.audio_responses = []
        
    async def connect(self):
        """Connect to the WebSocket server"""
        print(f"Connecting to {self.server_url}...")
        try:
            self.websocket = await websockets.connect(self.server_url)
            print("✅ Connected to server")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            print("Disconnected from server")
            self.websocket = None
            
    async def send_message(self, message):
        """Send a message to the server"""
        if not self.websocket:
            print("Not connected to server")
            return False
            
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except Exception as e:
            print(f"Error sending message: {e}")
            return False
    
    async def receive_message(self, timeout=5.0):
        """Receive a message from the server with timeout"""
        if not self.websocket:
            print("Not connected to server")
            return None
            
        try:
            message = await asyncio.wait_for(self.websocket.recv(), timeout=timeout)
            try:
                parsed = json.loads(message)
                self.message_history.append(parsed)
                return parsed
            except json.JSONDecodeError:
                print("Received non-JSON message")
                return message
        except asyncio.TimeoutError:
            print(f"Timeout waiting for message (after {timeout}s)")
            return None
        except Exception as e:
            print(f"Error receiving message: {e}")
            return None
    
    async def send_ping(self):
        """Send a ping message to the server"""
        print("\n=== Sending Ping ===")
        
        message = {
            "type": "ping",
            "timestamp": time.time()
        }
        
        if self.session_id:
            message["session_id"] = self.session_id
            
        if await self.send_message(message):
            print("Ping sent, waiting for pong...")
            
            # Wait for pong
            start_time = time.time()
            response = await self.receive_message(timeout=2.0)
            
            if response and response.get("type") == "pong":
                elapsed = time.time() - start_time
                print(f"Received pong in {elapsed*1000:.2f}ms")
                return True
            else:
                print("Did not receive pong response")
                return False
        else:
            return False
    
    async def send_audio(self, audio_data):
        """Send audio data to the server"""
        print("\n=== Sending Audio Data ===")
        
        # Encode audio data as base64
        encoded_audio = base64.b64encode(audio_data).decode('utf-8')
        
        message = {
            "type": "audio_data",
            "timestamp": time.time(),
            "data": encoded_audio
        }
        
        if self.session_id:
            message["session_id"] = self.session_id
            
        print(f"Sending {len(audio_data)} bytes of audio data...")
        
        if await self.send_message(message):
            print("Audio data sent")
            return True
        else:
            return False
    
    async def send_control(self, action):
        """Send a control message to the server"""
        print(f"\n=== Sending Control: {action} ===")
        
        message = {
            "type": "control",
            "action": action,
            "timestamp": time.time()
        }
        
        if self.session_id:
            message["session_id"] = self.session_id
            
        if await self.send_message(message):
            print(f"Control message '{action}' sent")
            return True
        else:
            return False
    
    async def wait_for_state(self, expected_state, timeout=30.0):
        """Wait for a specific state from the server"""
        print(f"Waiting for state: {expected_state}...")
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            response = await self.receive_message(timeout=1.0)
            
            if not response:
                continue
                
            if response.get("type") == "state_update":
                previous = response.get("previous")
                current = response.get("current")
                self.current_state = current
                
                print(f"State changed: {previous} → {current}")
                
                if current == expected_state:
                    print(f"✅ Reached expected state: {expected_state}")
                    return True
            
            # Handle other message types
            elif response.get("type") == "audio_response":
                print("Received audio response")
                self.audio_responses.append(response)
            elif response.get("type") == "error":
                code = response.get("code")
                error_message = response.get("message")
                print(f"⚠️ Received error: {code} - {error_message}")
        
        print(f"❌ Timeout waiting for state: {expected_state}")
        return False
    
    async def monitor_state_transitions(self, timeout=30.0):
        """Monitor state transitions for a period of time"""
        print(f"\n=== Monitoring State Transitions for {timeout}s ===")
        
        start_time = time.time()
        states = []
        
        while (time.time() - start_time) < timeout:
            response = await self.receive_message(timeout=1.0)
            
            if not response:
                continue
                
            if response.get("type") == "state_update":
                previous = response.get("previous")
                current = response.get("current")
                self.current_state = current
                
                state_info = {
                    "previous": previous,
                    "current": current,
                    "timestamp": time.time(),
                    "metadata": response.get("metadata", {})
                }
                
                states.append(state_info)
                
                print(f"State changed: {previous} → {current}")
                
                # Print additional info if available
                metadata = response.get("metadata", {})
                if "message" in metadata:
                    print(f"  Info: {metadata['message']}")
                if "transcript" in metadata:
                    print(f"  Transcript: {metadata['transcript']}")
            
            # Handle other message types
            elif response.get("type") == "audio_response":
                print(f"Received audio response ({len(response.get('data', ''))} bytes)")
                self.audio_responses.append(response)
            elif response.get("type") == "error":
                code = response.get("code")
                error_message = response.get("message")
                print(f"⚠️ Received error: {code} - {error_message}")
        
        print(f"\nObserved {len(states)} state transitions in {timeout}s")
        return states
    
    async def save_audio_response(self, response, directory="."):
        """Save received audio response to file"""
        if not response or response.get("type") != "audio_response":
            print("Not an audio response")
            return None
            
        try:
            # Decode audio data
            audio_bytes = base64.b64decode(response.get("data", ""))
            
            # Create output directory if it doesn't exist
            os.makedirs(directory, exist_ok=True)
            
            # Create a filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(directory, f"response_{timestamp}.wav")
            
            # Save the audio
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
                
            print(f"Saved audio response to {output_path} ({len(audio_bytes)} bytes)")
            return output_path
            
        except Exception as e:
            print(f"Error saving audio response: {e}")
            return None
    
    async def test_connection(self):
        """Test basic connection to the server"""
        print("\n=== Testing WebSocket Connection ===")
        
        connected = await self.connect()
        if not connected:
            return False
            
        # Wait for initial state (normally IDLE)
        try:
            response = await self.receive_message(timeout=5.0)
            
            if response and response.get("type") == "state_update":
                previous = response.get("previous")
                current = response.get("current")
                self.current_state = current
                
                print(f"Initial state: {current}")
                
                # Extract session_id if present
                self.session_id = response.get("session_id")
                if self.session_id:
                    print(f"Session ID: {self.session_id}")
                    
                return True
            else:
                print("Did not receive initial state update")
                return False
                
        except Exception as e:
            print(f"Error during connection test: {e}")
            return False
        finally:
            await self.disconnect()
    
    async def test_ping_pong(self):
        """Test ping/pong functionality"""
        print("\n=== Testing Ping/Pong ===")
        
        connected = await self.connect()
        if not connected:
            return False
            
        try:
            # Wait for initial state
            response = await self.receive_message(timeout=5.0)
            if response and response.get("type") == "state_update":
                self.session_id = response.get("session_id")
                self.current_state = response.get("current")
            
            # Send ping
            result = await self.send_ping()
            return result
                
        except Exception as e:
            print(f"Error during ping/pong test: {e}")
            return False
        finally:
            await self.disconnect()
    
    async def test_audio_pipeline(self, audio_file):
        """Test the full audio pipeline"""
        print(f"\n=== Testing Audio Pipeline with {audio_file} ===")
        
        # Load audio file
        if not os.path.exists(audio_file):
            print(f"Audio file not found: {audio_file}")
            return False
            
        try:
            with open(audio_file, "rb") as f:
                audio_data = f.read()
            
            print(f"Loaded {len(audio_data)} bytes from {audio_file}")
            
            # Try to parse with wave module to get info
            try:
                with wave.open(audio_file, 'rb') as wf:
                    channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                    sample_rate = wf.getframerate()
                    n_frames = wf.getnframes()
                    duration = n_frames / sample_rate
                    
                    print(f"Audio info: {duration:.2f}s, {channels} channel(s), {sample_rate} Hz, {sample_width*8} bits")
            except Exception as e:
                print(f"Could not parse audio info: {e}")
                
            # Connect to server
            connected = await self.connect()
            if not connected:
                return False
                
            # Wait for initial state
            response = await self.receive_message(timeout=5.0)
            if response and response.get("type") == "state_update":
                self.session_id = response.get("session_id")
                self.current_state = response.get("current")
                print(f"Initial state: {self.current_state}")
                
                # Test sequence:
                # 1. Send audio data
                # 2. Wait for LISTENING state
                # 3. Wait for PROCESSING state
                # 4. Wait for RESPONDING state
                # 5. Wait for WAITING state
                
                # Send audio data
                if not await self.send_audio(audio_data):
                    print("Failed to send audio data")
                    return False
                    
                # Monitor state transitions
                states = await self.monitor_state_transitions(timeout=60.0)
                
                # Check if we got through all the expected states
                expected_states = ["LISTENING", "PROCESSING", "RESPONDING", "WAITING"]
                observed_states = [s["current"] for s in states]
                
                success = all(state in observed_states for state in expected_states)
                
                if success:
                    print("✅ Successfully completed full audio pipeline")
                    
                    # Save any audio responses
                    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
                    os.makedirs(output_dir, exist_ok=True)
                    
                    for response in self.audio_responses:
                        await self.save_audio_response(response, output_dir)
                        
                    return True
                else:
                    missing_states = [s for s in expected_states if s not in observed_states]
                    print(f"❌ Did not observe all expected states. Missing: {missing_states}")
                    return False
            else:
                print("Did not receive initial state update")
                return False
                
        except Exception as e:
            print(f"Error during audio pipeline test: {e}")
            return False
        finally:
            await self.disconnect()
    
    async def test_error_handling(self):
        """Test server error handling"""
        print("\n=== Testing Error Handling ===")
        
        connected = await self.connect()
        if not connected:
            return False
            
        try:
            # Wait for initial state
            response = await self.receive_message(timeout=5.0)
            if response and response.get("type") == "state_update":
                self.session_id = response.get("session_id")
                self.current_state = response.get("current")
            
            # Test 1: Send malformed message
            print("\nTest 1: Sending malformed message")
            await self.websocket.send("This is not JSON")
            
            # Wait for error response
            response = await self.receive_message(timeout=5.0)
            error_received = response and response.get("type") == "error"
            
            if error_received:
                print(f"✅ Server correctly responded with error: {response.get('message')}")
            else:
                print("❌ Server did not send error response for malformed message")
            
            # Test 2: Send invalid message type
            print("\nTest 2: Sending invalid message type")
            message = {
                "type": "invalid_type",
                "timestamp": time.time()
            }
            
            if self.session_id:
                message["session_id"] = self.session_id
                
            await self.send_message(message)
            
            # Wait for error response
            response = await self.receive_message(timeout=5.0)
            error_received = response and response.get("type") == "error"
            
            if error_received:
                print(f"✅ Server correctly responded with error: {response.get('message')}")
            else:
                print("❌ Server did not send error response for invalid message type")
                
            # Test 3: Send empty audio data
            print("\nTest 3: Sending empty audio data")
            message = {
                "type": "audio_data",
                "timestamp": time.time(),
                "data": ""
            }
            
            if self.session_id:
                message["session_id"] = self.session_id
                
            await self.send_message(message)
            
            # Wait for error response
            response = await self.receive_message(timeout=5.0)
            error_received = response and response.get("type") == "error"
            
            if error_received:
                print(f"✅ Server correctly responded with error: {response.get('message')}")
            else:
                print("❌ Server did not send error response for empty audio data")
                
            return True
                
        except Exception as e:
            print(f"Error during error handling test: {e}")
            return False
        finally:
            await self.disconnect()
    
    async def test_multiple_connections(self, num_connections=3):
        """Test multiple simultaneous connections"""
        print(f"\n=== Testing {num_connections} Simultaneous Connections ===")
        
        connections = []
        
        try:
            # Establish multiple connections
            for i in range(num_connections):
                print(f"Establishing connection {i+1}...")
                websocket = await websockets.connect(self.server_url)
                connections.append(websocket)
                
                # Wait for initial message
                message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                try:
                    parsed = json.loads(message)
                    if parsed.get("type") == "state_update":
                        print(f"Connection {i+1} established with session ID: {parsed.get('session_id')}")
                except:
                    print(f"Connection {i+1} received non-JSON message")
            
            print(f"✅ Successfully established {len(connections)} simultaneous connections")
            
            # Send ping on each connection
            for i, websocket in enumerate(connections):
                try:
                    message = {
                        "type": "ping",
                        "timestamp": time.time()
                    }
                    
                    await websocket.send(json.dumps(message))
                    print(f"Sent ping on connection {i+1}")
                    
                    # Wait for pong
                    response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    try:
                        parsed = json.loads(response)
                        if parsed.get("type") == "pong":
                            print(f"Received pong on connection {i+1}")
                    except:
                        print(f"Connection {i+1} received non-JSON response")
                        
                except Exception as e:
                    print(f"Error on connection {i+1}: {e}")
            
            return True
                
        except Exception as e:
            print(f"Error during multiple connection test: {e}")
            return False
        finally:
            # Close all connections
            for websocket in connections:
                await websocket.close()
    
    async def run_all_tests(self, audio_file=None):
        """Run all WebSocket tests"""
        print("==== Running All WebSocket Tests ====")
        
        # Find test audio if none specified
        if not audio_file:
            # Try to find sample audio files
            tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sample_paths = [
                os.path.join(tools_dir, "output"),
                os.path.join(tools_dir, "samples"),
                os.path.join(os.path.dirname(tools_dir), "data", "audio", "uploads"),
            ]
            
            found = False
            for path in sample_paths:
                if os.path.exists(path):
                    for ext in ['.wav', '.mp3', '.ogg', '.webm']:
                        files = list(Path(path).glob(f'*{ext}'))
                        if files:
                            audio_file = str(files[0])
                            print(f"Found sample audio file: {audio_file}")
                            found = True
                            break
                if found:
                    break
        
        results = {}
        
        # Test 1: Basic connection
        print("\nRunning Test 1: Basic Connection")
        results["connection"] = await self.test_connection()
        
        # Test 2: Ping/Pong
        print("\nRunning Test 2: Ping/Pong")
        results["ping_pong"] = await self.test_ping_pong()
        
        # Test 3: Audio Pipeline (if audio file available)
        if audio_file and os.path.exists(audio_file):
            print(f"\nRunning Test 3: Audio Pipeline with {audio_file}")
            results["audio_pipeline"] = await self.test_audio_pipeline(audio_file)
        else:
            print("\nSkipping Test 3: No audio file available")
            results["audio_pipeline"] = None
        
        # Test 4: Error Handling
        print("\nRunning Test 4: Error Handling")
        results["error_handling"] = await self.test_error_handling()
        
        # Test 5: Multiple Connections
        print("\nRunning Test 5: Multiple Connections")
        results["multiple_connections"] = await self.test_multiple_connections(num_connections=2)
        
        # Test 6: Connection Stability (brief test)
        print("\nRunning Test 6: Connection Stability (10s)")
        connected = await self.connect()
        if connected:
            await asyncio.sleep(10)
            await self.disconnect()
            results["stability"] = True
        else:
            results["stability"] = False
        
        # Summary
        print("\n==== Test Summary ====")
        for test, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL" if result is not None else "⚠️ SKIPPED"
            print(f"{test}: {status}")
            
        return results

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="WebSocket Testing Tool")
    parser.add_argument("--url", default="ws://localhost:8765", help="WebSocket server URL")
    parser.add_argument("--test", choices=["all", "connection", "ping", "audio", "error", "multiple", "monitor"],
                        default="all", help="Specific test to run")
    parser.add_argument("--audio", help="Audio file for testing")
    parser.add_argument("--monitor", type=int, default=30, help="Monitoring duration in seconds")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = WebSocketTester(args.url)
    
    # Run selected test
    if args.test == "connection":
        await tester.test_connection()
    elif args.test == "ping":
        await tester.test_ping_pong()
    elif args.test == "audio":
        if args.audio:
            await tester.test_audio_pipeline(args.audio)
        else:
            print("No audio file specified. Use --audio to specify a file.")
    elif args.test == "error":
        await tester.test_error_handling()
    elif args.test == "multiple":
        await tester.test_multiple_connections()
    elif args.test == "monitor":
        connected = await tester.connect()
        if connected:
            await tester.monitor_state_transitions(timeout=args.monitor)
            await tester.disconnect()
    else:
        # Run all tests
        await tester.run_all_tests(args.audio)

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
