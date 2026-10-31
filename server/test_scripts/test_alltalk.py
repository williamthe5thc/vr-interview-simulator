#!/usr/bin/env python3
"""
AllTalk Voice Configuration Diagnostic Tool

This script diagnoses issues with AllTalk TTS voice configuration and helps fix
voice-related problems. It scans for available voices, checks configurations,
and provides guidance on fixing common issues.
"""

import os
import sys
import json
import time
import requests
import logging
from pathlib import Path
from pprint import pprint
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("alltalk_diagnostic.log")
    ]
)
logger = logging.getLogger("alltalk_diagnostic")

class AllTalkDiagnosticTool:
    def __init__(self, base_url="http://127.0.0.1:7851", alltalk_dir="D:/AllTalk/alltalk_tts"):
        self.base_url = base_url.rstrip('/')
        self.alltalk_dir = alltalk_dir
        self.voices_dir = os.path.join(self.alltalk_dir, "voices")
        self.outputs_dir = os.path.join(self.alltalk_dir, "outputs")
        self.server_settings = {}
        self.voices = []
        self.issues = []
        self.recommendations = []
        
        logger.info(f"AllTalk Diagnostic Tool initialized with:")
        logger.info(f"  Server URL: {self.base_url}")
        logger.info(f"  AllTalk directory: {self.alltalk_dir}")
        logger.info(f"  Voices directory: {self.voices_dir}")
        logger.info(f"  Outputs directory: {self.outputs_dir}")
        
    def run_diagnostics(self):
        """Run a full diagnostic scan of the AllTalk configuration"""
        print("="*70)
        print("AllTalk Voice Configuration Diagnostic Tool")
        print("="*70)
        
        # Check server availability
        if not self.check_server_connection():
            print("Cannot continue diagnostics without server connection.")
            return False
            
        # Get server settings
        self.get_server_settings()
        
        # Check for voice directories
        self.check_voice_directories()
        
        # Get list of voices from API
        self.get_api_voices()
        
        # Scan for actual voice files
        self.scan_voice_files()
        
        # Check for voice mapping issues
        self.check_voice_mapping()
        
        # Test a simple TTS request with default voice
        self.test_tts_request()
        
        # Display summary and recommendations
        self.display_summary()
        
        return True
        
    def check_server_connection(self) -> bool:
        """Check if we can connect to the AllTalk server"""
        print("\n[Checking server connection]")
        endpoints = ["/api/ready", "/ready", "/api/status", "/status"]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"  Trying {url}...")
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f"  ✓ Connected successfully to {endpoint}")
                    return True
            except Exception as e:
                print(f"  × Failed to connect to {endpoint}: {e}")
                
        self.issues.append("Cannot connect to AllTalk server")
        self.recommendations.append("Check if AllTalk server is running")
        return False
        
    def get_server_settings(self):
        """Get current settings from AllTalk server"""
        print("\n[Retrieving server settings]")
        try:
            response = requests.get(f"{self.base_url}/api/currentsettings", timeout=5)
            if response.status_code == 200:
                self.server_settings = response.json()
                print(f"  ✓ Retrieved settings")
                print(f"  • Current engine: {self.server_settings.get('current_engine_loaded', 'Unknown')}")
                print(f"  • Current model: {self.server_settings.get('current_model_loaded', 'Unknown')}")
                print(f"  • Manufacturer: {self.server_settings.get('manufacturer_name', 'Unknown')}")
                return True
        except Exception as e:
            print(f"  × Failed to get server settings: {e}")
            self.issues.append("Could not retrieve server settings")
            
        return False
        
    def check_voice_directories(self):
        """Check if voice directories exist and are accessible"""
        print("\n[Checking voice directories]")
        
        # Check AllTalk root directory
        if not os.path.exists(self.alltalk_dir):
            print(f"  × AllTalk directory does not exist: {self.alltalk_dir}")
            self.issues.append(f"AllTalk directory not found: {self.alltalk_dir}")
            self.recommendations.append(f"Update AllTalk directory path in your configuration")
            return False
        else:
            print(f"  ✓ AllTalk directory exists: {self.alltalk_dir}")
            
        # Check voices directory
        if not os.path.exists(self.voices_dir):
            print(f"  × Voices directory does not exist: {self.voices_dir}")
            self.issues.append(f"Voices directory not found: {self.voices_dir}")
            self.recommendations.append(f"Create voices directory: {self.voices_dir}")
            
            # Try to create voices directory
            try:
                os.makedirs(self.voices_dir, exist_ok=True)
                print(f"  ✓ Created missing voices directory: {self.voices_dir}")
            except Exception as e:
                print(f"  × Failed to create voices directory: {e}")
        else:
            print(f"  ✓ Voices directory exists: {self.voices_dir}")
            
        # Check outputs directory
        if not os.path.exists(self.outputs_dir):
            print(f"  × Outputs directory does not exist: {self.outputs_dir}")
            self.issues.append(f"Outputs directory not found: {self.outputs_dir}")
            self.recommendations.append(f"Create outputs directory: {self.outputs_dir}")
            
            # Try to create outputs directory
            try:
                os.makedirs(self.outputs_dir, exist_ok=True)
                print(f"  ✓ Created missing outputs directory: {self.outputs_dir}")
            except Exception as e:
                print(f"  × Failed to create outputs directory: {e}")
        else:
            print(f"  ✓ Outputs directory exists: {self.outputs_dir}")
            
        return True
        
    def get_api_voices(self):
        """Get list of voices from AllTalk API"""
        print("\n[Getting voices from API]")
        try:
            response = requests.get(f"{self.base_url}/api/voices", timeout=5)
            if response.status_code == 200:
                data = response.json()
                self.voices = data.get('voices', [])
                print(f"  ✓ Found {len(self.voices)} voices via API")
                for voice in self.voices[:5]:  # Show first 5 voices
                    print(f"    - {voice}")
                if len(self.voices) > 5:
                    print(f"    - ...and {len(self.voices) - 5} more")
                return True
        except Exception as e:
            print(f"  × Failed to get voices from API: {e}")
            self.issues.append("Could not retrieve voices from API")
            
        return False
        
    def scan_voice_files(self):
        """Scan for voice files in the voices directory"""
        print("\n[Scanning for voice files]")
        if not os.path.exists(self.voices_dir):
            print(f"  × Cannot scan voices: directory does not exist: {self.voices_dir}")
            return False
            
        voice_files = []
        try:
            for file in os.listdir(self.voices_dir):
                if file.endswith(('.wav', '.mp3')):
                    voice_files.append(file)
            
            print(f"  ✓ Found {len(voice_files)} voice files in {self.voices_dir}")
            for file in voice_files[:5]:  # Show first 5 voice files
                print(f"    - {file}")
            if len(voice_files) > 5:
                print(f"    - ...and {len(voice_files) - 5} more")
                
            # Compare with API voices
            if self.voices:
                api_set = set(self.voices)
                file_set = set(voice_files)
                
                missing_from_api = file_set - api_set
                missing_from_files = api_set - file_set
                
                if missing_from_api:
                    print(f"  ! {len(missing_from_api)} voice files not recognized by API")
                    for file in list(missing_from_api)[:3]:
                        print(f"    - {file}")
                    if len(missing_from_api) > 3:
                        print(f"    - ...and {len(missing_from_api) - 3} more")
                
                if missing_from_files:
                    print(f"  ! {len(missing_from_files)} voices from API not found as files")
                    for voice in list(missing_from_files)[:3]:
                        print(f"    - {voice}")
                    if len(missing_from_files) > 3:
                        print(f"    - ...and {len(missing_from_files) - 3} more")
                    
                    self.issues.append(f"API reports voices that don't exist as files")
                    self.recommendations.append("Create or download missing voice files")
                
            return True
        except Exception as e:
            print(f"  × Error scanning for voice files: {e}")
            self.issues.append("Error scanning for voice files")
            return False
    
    def check_voice_mapping(self):
        """Check for voice mapping issues"""
        print("\n[Checking voice mapping]")
        
        # Check if 'alloy' is being used (from error log)
        if "alloy" in self.voices:
            # Check if the file exists
            alloy_path = os.path.join(self.voices_dir, "alloy")
            if not os.path.exists(alloy_path):
                print(f"  × Voice 'alloy' is listed but file doesn't exist: {alloy_path}")
                self.issues.append("Using 'alloy' voice that doesn't exist as a file")
                
                # Check if there's an alloy.wav file instead
                if os.path.exists(alloy_path + ".wav"):
                    print(f"  ! Found 'alloy.wav' instead of 'alloy'")
                    self.recommendations.append("Voice names in API and file names might need .wav extension")
                else:
                    print(f"  ! 'alloy' voice file not found in any format")
                    self.recommendations.append("Create voice file for 'alloy' or change default voice")
        
        # Get the name of your local config file
        config_file = os.path.join(self.alltalk_dir, "config.yaml")
        if os.path.exists(config_file):
            print(f"  ✓ Found configuration file: {config_file}")
            try:
                with open(config_file, 'r') as f:
                    content = f.read()
                    # Check if there are voice-related settings
                    if 'voice:' in content:
                        print(f"  • Found voice settings in config.yaml")
                    if 'voice_samples_path:' in content:
                        print(f"  • Found voice samples path in config.yaml")
            except Exception as e:
                print(f"  × Error reading config file: {e}")
        else:
            print(f"  ! Configuration file not found: {config_file}")
            self.issues.append("Configuration file not found")
            
        return True
    
    def test_tts_request(self):
        """Test a simple TTS request to see what happens"""
        print("\n[Testing TTS request]")
        
        # Create a simple test request
        test_text = "This is a test of the AllTalk TTS system."
        output_file = f"test_{int(time.time())}"
        
        # First try the /api/voices to learn what voices are available
        try:
            response = requests.get(f"{self.base_url}/api/voices", timeout=5)
            if response.status_code == 200:
                voices = response.json().get('voices', [])
                if voices:
                    print(f"  ✓ Found {len(voices)} voices from API")
                    # Choose the first voice
                    test_voice = voices[0]
                    print(f"  • Using voice for test: {test_voice}")
                    
                    # Test if this voice file exists
                    voice_file = os.path.join(self.voices_dir, test_voice)
                    if not os.path.exists(voice_file):
                        print(f"  × Voice file doesn't exist: {voice_file}")
                        
                        # Check if adding .wav helps
                        if os.path.exists(voice_file + ".wav"):
                            print(f"  ! Voice file exists with .wav extension: {voice_file}.wav")
                            test_voice += ".wav"
                else:
                    print(f"  × No voices found from API")
                    self.issues.append("No voices available from API")
                    return False
            else:
                print(f"  × Failed to get voices: {response.status_code}")
                return False
        except Exception as e:
            print(f"  × Error getting voices: {e}")
            return False
        
        # Now try a TTS request
        try:
            print(f"  • Sending TTS request with voice: {test_voice}")
            response = requests.post(
                f"{self.base_url}/api/tts-generate",
                data={
                    "text_input": test_text,
                    "character_voice_gen": test_voice,
                    "output_file_name": output_file,
                    "format": "wav"
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            print(f"  • TTS response status: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✓ TTS request succeeded")
                
                # Check response content
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    try:
                        data = response.json()
                        print(f"  • Response: {json.dumps(data, indent=2)}")
                    except:
                        print(f"  ! Couldn't parse JSON response")
                else:
                    print(f"  • Got direct audio response: {len(response.content)} bytes")
                
                return True
            else:
                print(f"  × TTS request failed: {response.text}")
                self.issues.append(f"TTS request failed with status {response.status_code}")
                
                # Try a different endpoint
                print(f"  • Trying alternate TTS endpoint...")
                response = requests.post(
                    f"{self.base_url}/api/synthesize",
                    data={
                        "text": test_text,
                        "voice": test_voice,
                        "format": "wav"
                    },
                    headers={'Content-Type': 'application/x-www-form-urlencoded'},
                    timeout=30
                )
                
                print(f"  • Alternate TTS response status: {response.status_code}")
                if response.status_code == 200:
                    print(f"  ✓ Alternate TTS request succeeded")
                    return True
                else:
                    print(f"  × Alternate TTS request failed: {response.text}")
                    self.issues.append("All TTS endpoints failed")
                    return False
                
        except Exception as e:
            print(f"  × Error in TTS request: {e}")
            self.issues.append(f"Error in TTS request: {str(e)}")
            return False
    
    def display_summary(self):
        """Display a summary of the diagnostics"""
        print("\n" + "="*70)
        print("Diagnostic Summary")
        print("="*70)
        
        if self.issues:
            print("\nIssues Found:")
            for i, issue in enumerate(self.issues, 1):
                print(f"{i}. {issue}")
        else:
            print("\nNo issues found! Everything looks good.")
            
        if self.recommendations:
            print("\nRecommendations:")
            for i, rec in enumerate(self.recommendations, 1):
                print(f"{i}. {rec}")
        
        print("\nNext Steps:")
        if self.issues:
            # Common issue: voice files missing
            if any("voice" in issue.lower() for issue in self.issues):
                print("""
1. Check the voices directory and make sure voice files exist
2. Make sure voice files have the correct extensions (.wav)
3. Ensure voice names in the API match the filenames (with or without extensions)
4. Restart the AllTalk server after fixing issues
5. Update the VR Interview System configuration with correct voice names
                """)
            # If we couldn't connect to the server
            elif any("connect" in issue.lower() for issue in self.issues):
                print("""
1. Ensure the AllTalk server is running
2. Check if the URL and port are correct
3. Verify there are no firewall issues blocking connections
                """)
            else:
                print("""
1. Review the issues and recommendations above
2. Make necessary changes to the AllTalk configuration
3. Restart the AllTalk server
4. Re-run this diagnostic tool to confirm fixes
                """)
        else:
            print("""
1. Continue with VR Interview System configuration
2. Test with different voices to ensure all are working
3. Configure appropriate timeout values based on voice processing times
            """)
            
        print("="*70)

def fix_voice_files():
    """Helper function to fix common voice file issues"""
    print("\n" + "="*70)
    print("AllTalk Voice File Fixer")
    print("="*70)
    
    alltalk_dir = input("Enter AllTalk directory path [D:/AllTalk/alltalk_tts]: ").strip() or "D:/AllTalk/alltalk_tts"
    voices_dir = os.path.join(alltalk_dir, "voices")
    
    if not os.path.exists(voices_dir):
        print(f"Creating voices directory: {voices_dir}")
        try:
            os.makedirs(voices_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create voices directory: {e}")
            return
    
    # Check if there are .wav files in voices directory
    wav_files = []
    try:
        for file in os.listdir(voices_dir):
            if file.endswith('.wav'):
                wav_files.append(file)
    except Exception as e:
        print(f"Error scanning voices directory: {e}")
        return
    
    if not wav_files:
        print("No .wav files found in voices directory!")
        print("You need voice files for AllTalk to work.")
        print("Options:")
        print("1. Download sample voices from AllTalk website")
        print("2. Create your own voice files")
        print("3. Copy voice files from another installation")
        return
    
    print(f"Found {len(wav_files)} .wav files in voices directory.")
    
    # Check if there's a problem with 'alloy' voice
    if not os.path.exists(os.path.join(voices_dir, "alloy")) and any(file.startswith("alloy") for file in wav_files):
        alloy_file = next((file for file in wav_files if file.startswith("alloy")), None)
        if alloy_file:
            print(f"Found '{alloy_file}' but AllTalk is looking for 'alloy' without extension")
            
            # Offer to create a symlink or copy the file
            action = input("Create a copy without extension? (y/n): ").strip().lower()
            if action == 'y':
                try:
                    source = os.path.join(voices_dir, alloy_file)
                    target = os.path.join(voices_dir, "alloy")
                    import shutil
                    shutil.copy2(source, target)
                    print(f"Created copy: {source} -> {target}")
                except Exception as e:
                    print(f"Failed to create copy: {e}")
    
    # Check for other standard voices if they need fixing
    standard_voices = ["echo", "fable", "nova", "onyx", "shimmer"]
    
    for voice in standard_voices:
        if not os.path.exists(os.path.join(voices_dir, voice)) and any(file.startswith(voice) for file in wav_files):
            voice_file = next((file for file in wav_files if file.startswith(voice)), None)
            if voice_file:
                print(f"Found '{voice_file}' but AllTalk might be looking for '{voice}' without extension")
                
                # Offer to create copies for all missing standard voices at once
                action = input(f"Create a copy for '{voice}' without extension? (y/n): ").strip().lower()
                if action == 'y':
                    try:
                        source = os.path.join(voices_dir, voice_file)
                        target = os.path.join(voices_dir, voice)
                        import shutil
                        shutil.copy2(source, target)
                        print(f"Created copy: {source} -> {target}")
                    except Exception as e:
                        print(f"Failed to create copy: {e}")
    
    # Offer to update config file
    config_file = os.path.join(alltalk_dir, "config.yaml")
    if os.path.exists(config_file):
        print(f"\nFound configuration file: {config_file}")
        print("Would you like to check the voice configuration?")
        action = input("Check configuration? (y/n): ").strip().lower()
        if action == 'y':
            try:
                with open(config_file, 'r') as f:
                    config_content = f.read()
                
                # Check if there are voice configuration issues
                if 'voice:' in config_content:
                    print(f"Current voice configuration found in config file")
                    current_voice = None
                    import re
                    voice_match = re.search(r'voice:\s*([^\n]+)', config_content)
                    if voice_match:
                        current_voice = voice_match.group(1).strip()
                        print(f"Current voice setting: {current_voice}")
                        
                        # Check if this voice exists
                        if not os.path.exists(os.path.join(voices_dir, current_voice)):
                            print(f"Warning: Configured voice '{current_voice}' doesn't exist as a file")
                            
                            # Suggest a voice that does exist
                            if wav_files:
                                suggestion = wav_files[0].replace('.wav', '')
                                print(f"Would you like to update config to use '{suggestion}' instead?")
                                update = input("Update configuration? (y/n): ").strip().lower()
                                if update == 'y':
                                    new_config = config_content.replace(
                                        f'voice: {current_voice}',
                                        f'voice: {suggestion}'
                                    )
                                    # Backup original config
                                    import shutil
                                    backup_path = config_file + '.backup'
                                    shutil.copy2(config_file, backup_path)
                                    print(f"Created backup of config file: {backup_path}")
                                    
                                    # Write new config
                                    with open(config_file, 'w') as f:
                                        f.write(new_config)
                                    print(f"Updated config file with new voice: {suggestion}")
                                    print("You should restart the AllTalk server for changes to take effect")
            except Exception as e:
                print(f"Error checking configuration: {e}")
    
    print("\nVoice file fixes completed.")
    print("Restart the AllTalk server for changes to take effect.")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='AllTalk Voice Configuration Diagnostic Tool')
    parser.add_argument('--url', default='http://127.0.0.1:7851', help='AllTalk server URL')
    parser.add_argument('--dir', default='D:/AllTalk/alltalk_tts', help='AllTalk installation directory')
    parser.add_argument('--fix', action='store_true', help='Run the voice file fixer tool')
    
    if len(sys.argv) > 1:
        args = parser.parse_args()
        if args.fix:
            fix_voice_files()
            return
        
        # Run diagnostics with provided arguments
        tool = AllTalkDiagnosticTool(args.url, args.dir)
        tool.run_diagnostics()
    else:
        # Interactive mode
        print("AllTalk Voice Configuration Diagnostic Tool")
        print("-----------------------------------------")
        print("1. Run diagnostics")
        print("2. Fix voice files")
        print("3. Exit")
        
        choice = input("Select an option (1-3): ").strip()
        
        if choice == '1':
            url = input("Enter AllTalk server URL [http://127.0.0.1:7851]: ").strip() or "http://127.0.0.1:7851"
            alltalk_dir = input("Enter AllTalk directory path [D:/AllTalk/alltalk_tts]: ").strip() or "D:/AllTalk/alltalk_tts"
            
            tool = AllTalkDiagnosticTool(url, alltalk_dir)
            tool.run_diagnostics()
        elif choice == '2':
            fix_voice_files()
        elif choice == '3':
            print("Exiting.")
            sys.exit(0)
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

if __name__ == "__main__":
    import argparse
    main()