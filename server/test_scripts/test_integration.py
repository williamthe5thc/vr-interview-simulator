#!/usr/bin/env python3
"""
Integration Testing Tool

This script performs comprehensive integration testing of the entire VR Interview System,
including server startup, WebSocket connection, audio pipeline, and LLM integration.
"""

import sys
import os
import time
import json
import logging
import argparse
import asyncio
import subprocess
import signal
import requests
import websockets
import base64
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("integration_test")

class IntegrationTester:
    """Tests the full VR Interview System integration"""
    
    def __init__(self, config_path=None, server_url="ws://localhost:8765"):
        """Initialize the tester"""
        self.config_path = config_path
        self.server_url = server_url
        self.server_process = None
        self.websocket = None
        self.session_id = None
        
        # Find config file if not specified
        if not self.config_path:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            enhanced_config = os.path.join(project_root, "config_enhanced.json")
            default_config = os.path.join(project_root, "config.json")
            
            if os.path.exists(enhanced_config):
                self.config_path = enhanced_config
            elif os.path.exists(default_config):
                self.config_path = default_config
    
    async def start_server(self):
        """Start the server process"""
        print("Starting the server process...")
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        server_script = os.path.join(project_root, "server.py")
        
        if not os.path.exists(server_script):
            print(f"❌ Server script not found: {server_script}")
            return False
        
        cmd = [sys.executable, server_script]
        if self.config_path:
            print(f"Using config: {self.config_path}")
        
        try:
            # Start server process and redirect output to files
            log_dir = os.path.join(project_root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            stdout_file = open(os.path.join(log_dir, "integration_test_stdout.log"), "w")
            stderr_file = open(os.path.join(log_dir, "integration_test_stderr.log"), "w")
            
            self.server_process = subprocess.Popen(
                cmd,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=project_root,
                env=dict(os.environ, PYTHONPATH=project_root)
            )
            
            # Give the server time to start
            print("Waiting for server to start...")
            await asyncio.sleep(5)
            
            # Check if process is still running
            if self.server_process.poll() is not None:
                print(f"❌ Server process exited with code: {self.server_process.returncode}")
                return False
                
            print("✅ Server process started")
            return True
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def stop_server(self):
        """Stop the server process"""
        if self.server_process:
            print("Stopping server process...")
            
            try:
                # Try to terminate gracefully first
                if sys.platform == "win32":
                    self.server_process.send_signal(signal.CTRL_C_EVENT)
                else:
                    self.server_process.send_signal(signal.SIGINT)
                    
                # Wait a moment for graceful shutdown
                time.sleep(2)
                
                # Force kill if still running
                if self.server_process.poll() is None:
                    self.server_process.terminate()
                    time.sleep(1)
                    
                    if self.server_process.poll() is None:
                        self.server_process.kill()
                        
                print(f"Server process terminated with code: {self.server_process.returncode}")
                self.server_process = None
                
            except Exception as e:
                print(f"Error stopping server: {e}")
    
    async def connect_websocket(self):
        """Connect to the WebSocket server"""
        print(f"Connecting to WebSocket server at {self.server_url}...")
        
        try:
            self.websocket = await websockets.connect(self.server_url)
            
            # Wait for initial state message
            message = await asyncio.wait_for(self.websocket.recv(), timeout=5.0)
            try:
                parsed = json.loads(message)
                if parsed.get("type") == "state_update":
                    self.session_id = parsed.get("session_id")
                    print(f"✅ Connected with session ID: {self.session_id}")
                    return True
                else:
                    print(f"Received unexpected message type: {parsed.get('type')}")
                    return False
            except json.JSONDecodeError:
                print("Received non-JSON message")
                return False
                
        except asyncio.TimeoutError:
            print("Timeout waiting for initial message")
            return False
        except Exception as e:
            print(f"Error connecting to WebSocket: {e}")
            return False
    
    async def disconnect_websocket(self):
        """Disconnect from the WebSocket server"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            print("Disconnected from WebSocket server")
    
    async def check_ollama(self):
        """Check if Ollama is running and the model is available"""
        print("Checking Ollama service...")
        
        try:
            # Load config to get Ollama URL and model
            with open(self.config_path, "r") as f:
                config = json.load(f)
                
            ollama_url = config.get("ollama", {}).get("url", "http://localhost:11434")
            model = config.get("ollama", {}).get("model", "phi")
            
            # Check if Ollama is running
            response = requests.get(f"{ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                print(f"❌ Ollama service not available: Status {response.status_code}")
                return False
                
            # Check if model is available
            models = response.json().get("models", [])
            available_models = [m.get("name") for m in models]
            
            if model in available_models:
                print(f"✅ Ollama model '{model}' is available")
                return True
            else:
                print(f"❌ Model '{model}' not found in available models: {available_models}")
                
                # Provide instructions for downloading the model
                print(f"\nTo download the model, run: ollama pull {model}")
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Ollama service not available: {e}")
            print("\nPlease make sure Ollama is running. You can start it with:")
            print("  - Windows: Start the Ollama application")
            print("  - Linux/Mac: Run 'ollama serve' in a terminal")
            return False
        except Exception as e:
            print(f"❌ Error checking Ollama: {e}")
            return False
    
    async def check_alltalk(self):
        """Check if AllTalk is configured and running (if applicable)"""
        print("Checking AllTalk configuration...")
        
        try:
            # Load config to check if AllTalk is configured
            with open(self.config_path, "r") as f:
                config = json.load(f)
                
            alltalk_config = config.get("alltalk", {})
            if not alltalk_config:
                print("ℹ️ AllTalk is not configured, system will use gTTS fallback")
                return True
                
            alltalk_url = alltalk_config.get("url")
            if not alltalk_url:
                print("ℹ️ AllTalk URL not configured, system will use gTTS fallback")
                return True
                
            # Check if AllTalk is running
            print(f"Checking AllTalk service at {alltalk_url}...")
            response = requests.get(f"{alltalk_url}/api/ready", timeout=5)
            
            if response.status_code == 200 and response.text == "Ready":
                print("✅ AllTalk service is available")
                
                # Check voices
                voices_response = requests.get(f"{alltalk_url}/api/voices", timeout=5)
                if voices_response.status_code == 200:
                    voices_data = voices_response.json()
                    voice_count = len(voices_data.get("voices", []))
                    print(f"✅ AllTalk has {voice_count} voices available")
                else:
                    print("⚠️ Could not fetch AllTalk voices")
                    
                return True
            else:
                print(f"⚠️ AllTalk service not available: Status {response.status_code}")
                print("The system will use gTTS fallback, but TTS quality will be reduced")
                return True
                
        except requests.exceptions.RequestException as e:
            print(f"⚠️ AllTalk service not available: {e}")
            print("The system will use gTTS fallback, but TTS quality will be reduced")
            return True
        except Exception as e:
            print(f"⚠️ Error checking AllTalk: {e}")
            print("The system will use gTTS fallback, but TTS quality will be reduced")
            return True
    
    async def send_audio(self, audio_file):
        """Send audio to the server and wait for response"""
        print(f"Testing with audio file: {audio_file}")
        
        if not os.path.exists(audio_file):
            print(f"❌ Audio file not found: {audio_file}")
            return False
            
        try:
            # Load audio data
            with open(audio_file, "rb") as f:
                audio_data = f.read()
                
            # Encode as base64
            encoded_audio = base64.b64encode(audio_data).decode('utf-8')
            
            # Create message
            message = {
                "type": "audio_data",
                "timestamp": time.time(),
                "data": encoded_audio
            }
            
            if self.session_id:
                message["session_id"] = self.session_id
                
            # Send audio data
            print(f"Sending {len(audio_data)} bytes of audio data...")
            await self.websocket.send(json.dumps(message))
            
            # Monitor state changes and responses
            states = []
            audio_received = False
            start_time = time.time()
            
            # Wait for up to 60 seconds
            while (time.time() - start_time) < 60:
                try:
                    response = await asyncio.wait_for(self.websocket.recv(), timeout=1.0)
                    parsed = json.loads(response)
                    
                    if parsed.get("type") == "state_update":
                        previous = parsed.get("previous")
                        current = parsed.get("current")
                        states.append(current)
                        print(f"State changed: {previous} → {current}")
                        
                        # Print transcription if available
                        metadata = parsed.get("metadata", {})
                        if "transcript" in metadata:
                            print(f"Transcription: {metadata['transcript']}")
                            
                    elif parsed.get("type") == "audio_response":
                        print(f"Received audio response ({len(parsed.get('data', ''))} bytes)")
                        audio_received = True
                        
                        # Save audio
                        audio_bytes = base64.b64decode(parsed.get("data", ""))
                        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
                        os.makedirs(output_dir, exist_ok=True)
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        output_path = os.path.join(output_dir, f"integration_test_{timestamp}.wav")
                        
                        with open(output_path, "wb") as f:
                            f.write(audio_bytes)
                            print(f"Saved audio to {output_path}")
                            
                    elif parsed.get("type") == "error":
                        code = parsed.get("code")
                        error_message = parsed.get("message")
                        print(f"❌ Received error: {code} - {error_message}")
                    
                    # Check if we've completed the full pipeline
                    if current == "WAITING" and audio_received:
                        print("✅ Full pipeline completed successfully")
                        break
                        
                except asyncio.TimeoutError:
                    # Just a timeout on the single receive, continue
                    continue
                except Exception as e:
                    print(f"❌ Error receiving messages: {e}")
                    return False
            
            # Check if we got through the expected states
            expected_states = ["LISTENING", "PROCESSING", "RESPONDING", "WAITING"]
            success = all(state in states for state in expected_states)
            
            if success and audio_received:
                print("✅ End-to-end test completed successfully")
                return True
            else:
                missing_states = [s for s in expected_states if s not in states]
                if missing_states:
                    print(f"❌ Did not observe all expected states. Missing: {missing_states}")
                if not audio_received:
                    print("❌ Did not receive audio response")
                return False
                
        except Exception as e:
            print(f"❌ Error during audio test: {e}")
            return False
    
    async def run_full_test(self, audio_file=None):
        """Run a full integration test"""
        print("==== Running Full Integration Test ====")
        print(f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find a test audio file if none specified
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
                    
            if not audio_file:
                print("❌ No audio file specified and no samples found")
                print("Please provide an audio file with --audio")
                return False
        
        # Track test results
        results = {}
        
        try:
            # Step 1: Check dependencies
            print("\n--- Step 1: Checking Dependencies ---")
            
            # Check Ollama
            results["ollama"] = await self.check_ollama()
            if not results["ollama"]:
                print("⚠️ Ollama check failed, but continuing with other tests")
                
            # Check AllTalk (optional)
            results["alltalk"] = await self.check_alltalk()
            
            # Step 2: Start the server
            print("\n--- Step 2: Starting Server ---")
            results["server_start"] = await self.start_server()
            if not results["server_start"]:
                print("❌ Server failed to start, cannot continue with tests")
                return False
                
            # Step 3: Connect to WebSocket
            print("\n--- Step 3: Connecting to WebSocket ---")
            results["websocket"] = await self.connect_websocket()
            if not results["websocket"]:
                print("❌ WebSocket connection failed, cannot continue with tests")
                return False
                
            # Step 4: Send audio and test full pipeline
            print("\n--- Step 4: Testing Audio Pipeline ---")
            results["audio_pipeline"] = await self.send_audio(audio_file)
            
            # Overall success
            success = results["websocket"] and results["audio_pipeline"]
            
            # Summary
            print("\n==== Test Summary ====")
            for test, result in results.items():
                status = "✅ PASS" if result else "❌ FAIL"
                print(f"{test}: {status}")
                
            if success:
                print("\n✅ Integration test completed successfully")
            else:
                print("\n❌ Integration test failed")
                
            return success
            
        except Exception as e:
            print(f"\n❌ Error during integration test: {e}")
            import traceback
            print(traceback.format_exc())
            return False
        finally:
            # Clean up
            print("\n--- Cleaning Up ---")
            
            # Disconnect WebSocket
            await self.disconnect_websocket()
            
            # Stop server
            self.stop_server()
            
            print("Integration test complete")

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Integration Testing Tool")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--url", default="ws://localhost:8765", help="WebSocket server URL")
    parser.add_argument("--audio", help="Audio file for testing")
    parser.add_argument("--no-server", action="store_true", help="Don't start the server (use existing)")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = IntegrationTester(args.config, args.url)
    
    if args.no_server:
        # Just run the WebSocket tests against an existing server
        try:
            # Check Ollama
            await tester.check_ollama()
            
            # Check AllTalk
            await tester.check_alltalk()
            
            # Connect to WebSocket
            connected = await tester.connect_websocket()
            if not connected:
                print("❌ WebSocket connection failed")
                return 1
                
            # Send audio
            if args.audio:
                await tester.send_audio(args.audio)
            else:
                print("No audio file specified for testing")
                
        finally:
            # Disconnect WebSocket
            await tester.disconnect_websocket()
    else:
        # Run full integration test
        success = await tester.run_full_test(args.audio)
        return 0 if success else 1

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
