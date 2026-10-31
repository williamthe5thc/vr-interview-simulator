#!/usr/bin/env python3
"""
AllTalk TTS Testing Tool

This script tests the AllTalk text-to-speech service integration 
with the VR Interview System. It can list available voices, test
specific voices, and update configuration.
"""

import sys
import os
import json
import requests
import time
import argparse
from pathlib import Path
import subprocess

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

class AllTalkTester:
    def __init__(self, url="http://127.0.0.1:7851", config_file="config_enhanced.json"):
        self.url = url
        if not self.url.startswith("http"):
            self.url = f"http://{self.url}"
        
        self.config_file = config_file
        self.current_voice = self._get_current_voice()
    
    def _get_current_voice(self):
        """Get current voice from config"""
        try:
            # Find config file if path is relative
            config_file = self.config_file
            if not os.path.isabs(config_file):
                # Try in the current directory
                if not os.path.exists(config_file):
                    # Try in the parent directory
                    parent_config = os.path.join("..", "..", config_file)
                    if os.path.exists(parent_config):
                        config_file = parent_config
                        
            with open(config_file, 'r') as f:
                config = json.load(f)
            alltalk_config = config.get("alltalk", {})
            return alltalk_config.get("voice", "")
        except Exception as e:
            print(f"⚠️ Couldn't load config: {e}")
            return ""
    
    def check_connection(self):
        """Check if AllTalk is available"""
        print(f"Checking AllTalk connection at {self.url}...")
        try:
            response = requests.get(f"{self.url}/api/ready", timeout=5)
            if response.text == "Ready":
                print("✅ AllTalk server is ready!")
                return True
            else:
                print(f"❌ AllTalk returned unexpected response: {response.text}")
                return False
        except Exception as e:
            print(f"❌ AllTalk connection failed: {e}")
            return False
    
    def get_voices(self):
        """Get list of available voices"""
        try:
            response = requests.get(f"{self.url}/api/voices", timeout=5)
            if response.status_code != 200:
                print(f"❌ Failed to get voices: {response.status_code}")
                return []
                
            voices_data = response.json()
            voices = voices_data.get("voices", [])
            
            # Handle different response formats
            if voices and isinstance(voices[0], dict) and "voice_file" in voices[0]:
                return [v["voice_file"] for v in voices]
            
            return voices
        except Exception as e:
            print(f"❌ Error getting voices: {e}")
            return []
    
    def test_voice(self, voice, text):
        """Test a voice with sample text"""
        print(f"\nTesting voice: {voice}")
        print(f"Sample text: \"{text}\"")
        
        try:
            # Create request data
            data = {
                "text_input": text,
                "character_voice_gen": voice,
                "narrator_enabled": "false",
                "language": "en",
                "output_file_name": f"test_{int(time.time())}"
            }
            
            # Send request
            print("Sending request to AllTalk...")
            start_time = time.time()
            response = requests.post(f"{self.url}/api/tts-generate", data=data, timeout=30)
            
            if response.status_code != 200:
                print(f"❌ TTS generation failed: {response.status_code}")
                print(f"Error: {response.text}")
                return False
                
            # Parse response
            result = response.json()
            if "output_file_url" not in result:
                print(f"❌ No output file URL in response")
                return False
                
            # Download the audio
            audio_url = f"{self.url}{result['output_file_url']}"
            print(f"✅ Audio generated successfully: {audio_url}")
            
            # Download and save the audio
            audio_response = requests.get(audio_url, timeout=10)
            if audio_response.status_code != 200:
                print(f"❌ Failed to download audio: {audio_response.status_code}")
                return False
                
            # Save to file
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            voice_name = voice.replace(" ", "_").replace(".", "").replace("(", "").replace(")", "")
            output_file = os.path.join(output_dir, f"test_{voice_name}.wav")
            
            with open(output_file, "wb") as f:
                f.write(audio_response.content)
                
            duration = time.time() - start_time
            print(f"✅ Audio saved to {output_file} ({len(audio_response.content)} bytes in {duration:.2f}s)")
            
            # Try to play the audio on Windows
            if sys.platform == 'win32':
                try:
                    print("▶️ Playing audio...")
                    subprocess.Popen(["start", output_file], shell=True)
                except Exception as e:
                    print(f"⚠️ Couldn't play audio automatically: {e}")
                    
            return True
        except Exception as e:
            print(f"❌ Error testing voice: {e}")
            return False
    
    def update_config(self, voice):
        """Update the configuration with the selected voice"""
        try:
            # Find config file if path is relative
            config_file = self.config_file
            if not os.path.isabs(config_file):
                # Try in the current directory
                if not os.path.exists(config_file):
                    # Try in the parent directory
                    parent_config = os.path.join("..", "..", config_file)
                    if os.path.exists(parent_config):
                        config_file = parent_config
                        
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            if "alltalk" not in config:
                config["alltalk"] = {}
                
            config["alltalk"]["voice"] = voice
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
            print(f"✅ Updated config file {config_file} with voice: {voice}")
            self.current_voice = voice
            return True
        except Exception as e:
            print(f"❌ Error updating config: {e}")
            return False
    
    def list_voices(self, voices):
        """Display available voices"""
        print("\nAvailable voices:")
        print("=================")
        for i, voice in enumerate(voices):
            current = " (current)" if voice == self.current_voice else ""
            print(f"{i+1}. {voice}{current}")
    
    def interactive(self, voices, default_text):
        """Run interactive mode"""
        print("\nInteractive Mode")
        print("===============")
        
        while True:
            action = input("\nChoose an action (t=test, s=set, l=list, q=quit): ").lower()
            
            if action == 'q':
                break
                
            elif action == 'l':
                self.list_voices(voices)
            
            elif action == 't':
                voice_input = input("\nEnter voice number or name to test (or press Enter for current): ")
                
                if not voice_input.strip():
                    voice_to_test = self.current_voice
                    if not voice_to_test or voice_to_test not in voices:
                        print("⚠️ No current voice set. Using first available voice.")
                        voice_to_test = voices[0]
                else:
                    try:
                        index = int(voice_input) - 1
                        if 0 <= index < len(voices):
                            voice_to_test = voices[index]
                        else:
                            print(f"⚠️ Invalid voice number. Using first available voice.")
                            voice_to_test = voices[0]
                    except ValueError:
                        if voice_input in voices:
                            voice_to_test = voice_input
                        else:
                            print(f"⚠️ Voice '{voice_input}' not found. Using first available voice.")
                            voice_to_test = voices[0]
                
                # Get custom text
                text_input = input("\nEnter test text (or press Enter for default): ")
                if text_input.strip():
                    test_text = text_input
                else:
                    test_text = default_text
                
                # Test the voice
                self.test_voice(voice_to_test, test_text)
                
            elif action == 's':
                voice_input = input("\nEnter voice number or name to set as default: ")
                
                try:
                    index = int(voice_input) - 1
                    if 0 <= index < len(voices):
                        voice_to_set = voices[index]
                    else:
                        print(f"⚠️ Invalid voice number.")
                        continue
                except ValueError:
                    if voice_input in voices:
                        voice_to_set = voice_input
                    else:
                        print(f"⚠️ Voice '{voice_input}' not found.")
                        continue
                
                # Confirm
                confirm = input(f"Set '{voice_to_set}' as default voice? (y/n): ")
                if confirm.lower() == 'y':
                    if self.update_config(voice_to_set):
                        # Ask if user wants to test
                        test_confirm = input("Test this voice now? (y/n): ")
                        if test_confirm.lower() == 'y':
                            self.test_voice(voice_to_set, default_text)
            
            else:
                print("Unknown action. Choose t, s, l, or q.")

def main():
    # Parse arguments
    parser = argparse.ArgumentParser(description="AllTalk Voice Test")
    parser.add_argument("--url", default="http://127.0.0.1:7851", help="AllTalk server URL")
    parser.add_argument("--config", default="config_enhanced.json", help="Config file path")
    parser.add_argument("--list", action="store_true", help="List available voices")
    parser.add_argument("--test", help="Test a specific voice")
    parser.add_argument("--set", help="Set a voice in the config")
    parser.add_argument("--text", default="This is a test of the AllTalk text-to-speech system with the VR Interview System.", 
                      help="Text to use for testing")
    args = parser.parse_args()
    
    print("\n==== AllTalk Voice Test ====\n")
    
    # Initialize tester
    tester = AllTalkTester(args.url, args.config)
    
    # Check connection
    if not tester.check_connection():
        print("\nTroubleshooting suggestions:")
        print("1. Make sure AllTalk server is running")
        print("2. Check the URL and port are correct")
        print("3. Verify network settings if running on a different machine")
        return 1
    
    # Get voices
    voices = tester.get_voices()
    if not voices:
        print("❌ No voices found. Please check AllTalk installation.")
        return 1
    
    print(f"\nFound {len(voices)} voices")
    
    # List voices if requested
    if args.list or not (args.test or args.set):
        tester.list_voices(voices)
    
    # Test a voice if requested
    if args.test:
        voice_to_test = args.test
        if voice_to_test not in voices:
            # Try to find by number
            try:
                index = int(voice_to_test) - 1
                if 0 <= index < len(voices):
                    voice_to_test = voices[index]
                else:
                    print(f"❌ Invalid voice number: {voice_to_test}")
                    return 1
            except ValueError:
                print(f"⚠️ Voice '{voice_to_test}' not found. Using first available voice.")
                voice_to_test = voices[0]
        
        tester.test_voice(voice_to_test, args.text)
    
    # Set a voice if requested
    if args.set:
        voice_to_set = args.set
        if voice_to_set not in voices:
            # Try to find by number
            try:
                index = int(voice_to_set) - 1
                if 0 <= index < len(voices):
                    voice_to_set = voices[index]
                else:
                    print(f"❌ Invalid voice number: {voice_to_set}")
                    return 1
            except ValueError:
                print(f"⚠️ Voice '{voice_to_set}' not found. Using first available voice.")
                voice_to_set = voices[0]
        
        tester.update_config(voice_to_set)
    
    # If no specific action, run interactive mode
    if not (args.list or args.test or args.set):
        tester.interactive(voices, args.text)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
