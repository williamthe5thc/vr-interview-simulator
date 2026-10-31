#!/usr/bin/env python3
"""
Fixed Piper Voice Tester

This script tests AllTalk Piper voices with correctly formatted output filenames.
"""

import os
import time
import json
import requests
import re
from datetime import datetime

class FixedPiperTester:
    def __init__(self, base_url="http://127.0.0.1:7851", output_dir="voice_test_results"):
        self.base_url = base_url.rstrip('/')
        self.output_dir = output_dir
        self.results = []
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
    def sanitize_filename(self, filename):
        """Remove special characters and file extensions from filename"""
        # Remove file extension
        filename = os.path.splitext(filename)[0]
        
        # Replace special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', filename)
        
        # Ensure it's not empty
        if not sanitized:
            sanitized = "output"
            
        return sanitized
        
    def check_server(self):
        """Check if AllTalk server is available"""
        print("Checking AllTalk server...")
        try:
            response = requests.get(f"{self.base_url}/api/ready", timeout=5)
            if response.status_code == 200:
                print("✓ AllTalk server is available")
                return True
            else:
                print(f"× AllTalk server returned: {response.status_code}")
                return False
        except Exception as e:
            print(f"× Error connecting to AllTalk server: {e}")
            return False
    
    def get_voices(self):
        """Get available voices from the server"""
        print("\nGetting available voices...")
        try:
            response = requests.get(f"{self.base_url}/api/voices", timeout=5)
            if response.status_code == 200:
                data = response.json()
                voices = data.get('voices', [])
                
                # Filter for onnx files (Piper voices)
                piper_voices = [v for v in voices if v.endswith('.onnx')]
                print(f"Found {len(piper_voices)} Piper voices")
                return piper_voices
            else:
                print(f"× Failed to get voices: {response.status_code}")
                return []
        except Exception as e:
            print(f"× Error getting voices: {e}")
            return []
    
    def test_voice(self, voice, test_text="This is a test of the voice for the VR Interview System."):
        """Test a specific voice and save the audio file"""
        print(f"\nTesting voice: {voice}")
        
        # Create a sanitized output filename - crucial for AllTalk API
        voice_name = self.sanitize_filename(voice)
        output_file = f"test_{voice_name}"
        
        print(f"Using output filename: {output_file}")
        
        try:
            # Time the request
            start_time = time.time()
            
            # Try synthesize endpoint first
            try:
                response = requests.post(
                    f"{self.base_url}/api/synthesize",
                    data={
                        "text": test_text,
                        "voice": voice,
                        "format": "wav"
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=60
                )
                
                # If successful, save the audio
                if response.status_code == 200 and len(response.content) > 1000:
                    elapsed = time.time() - start_time
                    print(f"✓ Voice generation successful using /api/synthesize in {elapsed:.2f} seconds")
                    
                    # Save the audio file locally
                    dest_path = os.path.join(self.output_dir, f"{voice_name}.wav")
                    with open(dest_path, 'wb') as f:
                        f.write(response.content)
                    print(f"✓ Saved audio file: {dest_path}")
                    
                    result = {
                        "voice": voice,
                        "time": elapsed,
                        "success": True,
                        "endpoint": "synthesize",
                        "file_size": len(response.content)
                    }
                    self.results.append(result)
                    return result
                else:
                    print(f"× Synthesize endpoint failed: {response.status_code}")
            except Exception as e:
                print(f"× Error with synthesize endpoint: {e}")
            
            # If synthesize failed, try tts-generate
            try:
                response = requests.post(
                    f"{self.base_url}/api/tts-generate",
                    data={
                        "text_input": test_text,
                        "character_voice_gen": voice,
                        "output_file_name": output_file,
                        "format": "wav"
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=60
                )
                
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    print(f"✓ Voice generation successful using /api/tts-generate in {elapsed:.2f} seconds")
                    
                    # Save the audio file locally if direct response
                    if 'application/json' not in response.headers.get('Content-Type', ''):
                        dest_path = os.path.join(self.output_dir, f"{voice_name}.wav")
                        with open(dest_path, 'wb') as f:
                            f.write(response.content)
                        print(f"✓ Saved audio file: {dest_path}")
                        
                        result = {
                            "voice": voice,
                            "time": elapsed,
                            "success": True,
                            "endpoint": "tts-generate-direct",
                            "file_size": len(response.content)
                        }
                        self.results.append(result)
                        return result
                    else:
                        # Handle JSON response with file info
                        try:
                            result_data = response.json()
                            print(f"Response: {json.dumps(result_data, indent=2)}")
                            
                            if 'output_file_path' in result_data:
                                src_path = result_data['output_file_path']
                                if os.path.exists(src_path):
                                    # Copy the file to our output directory
                                    with open(src_path, 'rb') as src_file:
                                        dest_path = os.path.join(self.output_dir, f"{voice_name}.wav")
                                        with open(dest_path, 'wb') as dest_file:
                                            audio_data = src_file.read()
                                            dest_file.write(audio_data)
                                        print(f"✓ Saved audio file from path: {dest_path}")
                                        
                                        result = {
                                            "voice": voice,
                                            "time": elapsed,
                                            "success": True,
                                            "endpoint": "tts-generate-file",
                                            "file_size": len(audio_data)
                                        }
                                        self.results.append(result)
                                        return result
                                else:
                                    print(f"× Output file not found: {src_path}")
                                    
                                    # Try checking in outputs directory
                                    alltalk_dir = "D:/AllTalk/alltalk_tts"
                                    outputs_dir = os.path.join(alltalk_dir, "outputs")
                                    for filename in os.listdir(outputs_dir):
                                        if output_file in filename:
                                            full_path = os.path.join(outputs_dir, filename)
                                            with open(full_path, 'rb') as src_file:
                                                dest_path = os.path.join(self.output_dir, f"{voice_name}.wav")
                                                with open(dest_path, 'wb') as dest_file:
                                                    audio_data = src_file.read()
                                                    dest_file.write(audio_data)
                                                print(f"✓ Found and saved file: {dest_path}")
                                                
                                                result = {
                                                    "voice": voice,
                                                    "time": elapsed,
                                                    "success": True,
                                                    "endpoint": "tts-generate-found",
                                                    "file_size": len(audio_data)
                                                }
                                                self.results.append(result)
                                                return result
                        except Exception as e:
                            print(f"× Error processing JSON response: {e}")
                else:
                    print(f"× Voice generation failed: {response.status_code}")
                    if response.text:
                        print(f"Error: {response.text}")
            except Exception as e:
                print(f"× Error with tts-generate endpoint: {e}")
            
            # If all attempts failed, record failure
            result = {
                "voice": voice,
                "time": time.time() - start_time,
                "success": False,
                "error": "All endpoints failed"
            }
            self.results.append(result)
            return result
        except Exception as e:
            print(f"× Error testing voice: {e}")
            
            # Store the error
            result = {
                "voice": voice,
                "time": 0,
                "success": False,
                "error": str(e)
            }
            self.results.append(result)
            return result
    
    def test_piper_voices(self, voice_filter=None, max_voices=None):
        """Test all Piper voices or a filtered subset"""
        if not self.check_server():
            print("Cannot continue without server connection")
            return False
        
        # Get voices
        voices = self.get_voices()
        if not voices:
            print("No voices available for testing")
            return False
        
        # Filter voices if requested
        if voice_filter:
            filtered_voices = [v for v in voices if voice_filter in v]
            if filtered_voices:
                voices = filtered_voices
                print(f"Filtered to {len(voices)} voices containing '{voice_filter}'")
            else:
                print(f"No voices found matching '{voice_filter}', using all voices")
        
        # Limit number of voices if requested
        if max_voices and len(voices) > max_voices:
            voices = voices[:max_voices]
            print(f"Limited to {max_voices} voices")
        
        # Start the test
        print(f"\nTesting {len(voices)} voices:")
        for voice in voices:
            print(f"- {voice}")
        
        print("\nStarting tests...")
        start_time = time.time()
        
        for i, voice in enumerate(voices):
            print(f"\nTesting voice {i+1}/{len(voices)}: {voice}")
            self.test_voice(voice)
        
        # Calculate total time
        total_time = time.time() - start_time
        print(f"\nTests completed in {total_time:.2f} seconds")
        
        # Generate a simple report
        self.generate_report()
        return True
    
    def generate_report(self):
        """Generate a simple report of the test results"""
        if not self.results:
            print("No test results to report")
            return
        
        # Count successes and failures
        successful = sum(1 for r in self.results if r.get('success'))
        failed = len(self.results) - successful
        
        # Create report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(self.output_dir, f"voice_test_report_{timestamp}.txt")
        
        with open(report_path, 'w') as f:
            f.write("=== Piper Voice Test Report ===\n\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Voices tested: {len(self.results)}\n")
            f.write(f"Successful: {successful}\n")
            f.write(f"Failed: {failed}\n\n")
            
            f.write("=== Voice Rankings by Speed ===\n\n")
            
            # Sort results by processing time
            successful_results = [r for r in self.results if r.get('success')]
            successful_results.sort(key=lambda r: r.get('time', float('inf')))
            
            for i, result in enumerate(successful_results):
                f.write(f"{i+1}. {result['voice']}: {result.get('time', 0):.2f} seconds, " 
                        f"via {result.get('endpoint', 'unknown')}\n")
            
            f.write("\n=== Full Results ===\n\n")
            for result in self.results:
                status = "Success" if result.get('success') else "Failed"
                if result.get('success'):
                    f.write(f"{result['voice']}: {status}, {result.get('time', 0):.2f} seconds, " 
                            f"via {result.get('endpoint', 'unknown')}, "
                            f"{result.get('file_size', 0)} bytes\n")
                else:
                    f.write(f"{result['voice']}: {status}, Error: {result.get('error', 'Unknown')}\n")
        
        print(f"\nReport generated: {report_path}")
        
        # Also save as JSON
        json_path = os.path.join(self.output_dir, f"voice_test_results_{timestamp}.json")
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"Results saved as JSON: {json_path}")
        
        # Print recommendations
        if successful_results:
            fastest = successful_results[0]
            print("\n=== Recommendations ===")
            print(f"Fastest voice: {fastest['voice']} ({fastest.get('time', 0):.2f} seconds)")
            
            # Recommend timeout setting
            max_time = max(r.get('time', 0) for r in successful_results)
            recommended_timeout = max(60, int(max_time * 1.5))
            print(f"Recommended timeout: {recommended_timeout} seconds")
            
            # Create a sample config
            config = {
                "alltalk": {
                    "url": "http://127.0.0.1:7851", 
                    "voice": fastest['voice'],
                    "format": "wav",
                    "retries": 3,
                    "timeout": recommended_timeout,
                    "direct_api_timeout": recommended_timeout + 30,
                    "alltalk_dir": "D:/AllTalk/alltalk_tts",
                    "default_language": "en"
                }
            }
            
            config_path = os.path.join(self.output_dir, "recommended_alltalk_config.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"Generated recommended config: {config_path}")

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Fixed Piper Voice Tester")
    parser.add_argument("--url", default="http://127.0.0.1:7851", help="AllTalk server URL")
    parser.add_argument("--output", default="voice_test_results", help="Output directory")
    parser.add_argument("--filter", help="Filter voices containing this string")
    parser.add_argument("--max", type=int, help="Maximum number of voices to test")
    parser.add_argument("--single", help="Test only a single voice by name")
    parser.add_argument("--text", default="This is a test of the voice for the VR Interview System.", 
                        help="Test text to use for voice generation")
    
    args = parser.parse_args()
    
    tester = FixedPiperTester(args.url, args.output)
    
    if args.single:
        # Test a single voice
        print(f"Testing single voice: {args.single}")
        if tester.check_server():
            result = tester.test_voice(args.single, args.text)
            if result.get('success'):
                print(f"\nVoice test successful: {result.get('time', 0):.2f} seconds")
                print(f"Recommended timeout: {int(result.get('time', 30) * 1.5)} seconds")
            else:
                print(f"\nVoice test failed: {result.get('error', 'Unknown error')}")
    else:
        # Test multiple voices
        tester.test_piper_voices(args.filter, args.max)

if __name__ == "__main__":
    main()