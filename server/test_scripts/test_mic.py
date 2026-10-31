#!/usr/bin/env python3
"""
Microphone Testing Tool

This script provides utilities for testing microphone input,
listing available devices, and recording/playing back audio.
"""

import pyaudio
import wave
import numpy as np
import os
import sys
import argparse
import time
from datetime import datetime
import platform

# Audio recording parameters
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
SILENCE_THRESHOLD = 500  # Adjust based on environment
MIN_SILENCE_DURATION = 1.5  # Seconds of silence to consider speech ended
MAX_RECORDING_DURATION = 30  # Maximum recording duration in seconds

class MicrophoneTester:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        
    def __del__(self):
        """Clean up PyAudio when done"""
        if hasattr(self, 'p'):
            self.p.terminate()
    
    def list_devices(self):
        """List all available microphone devices"""
        print("Available microphone devices:")
        print("-----------------------------")
        
        devices = []
        default_index = self.p.get_default_input_device_info().get('index')
        
        for i in range(self.p.get_device_count()):
            device_info = self.p.get_device_info_by_index(i)
            
            # Only show input devices
            if device_info.get('maxInputChannels') > 0:
                is_default = device_info.get('index') == default_index
                devices.append({
                    'index': i,
                    'name': device_info.get('name'),
                    'channels': device_info.get('maxInputChannels'),
                    'sample_rate': device_info.get('defaultSampleRate'),
                    'is_default': is_default
                })
                
                print(f"Device {i}: {device_info.get('name')}")
                print(f"  Input channels: {device_info.get('maxInputChannels')}")
                print(f"  Default sample rate: {device_info.get('defaultSampleRate')}")
                print(f"  Default: {'Yes' if is_default else 'No'}")
                print()
                
        # Show the default device
        default_device = self.p.get_default_input_device_info()
        print(f"Default input device: {default_device.get('name')} (Device {default_device.get('index')})")
        
        return devices
    
    def is_silent(self, data):
        """Check if the audio chunk is silent"""
        # Convert bytes to numpy array
        data_np = np.frombuffer(data, dtype=np.int16)
        # Calculate RMS amplitude
        rms = np.sqrt(np.mean(np.square(data_np)))
        return rms < SILENCE_THRESHOLD
    
    def record_audio(self, output_dir=".", device_index=None, duration=None, 
                     auto_stop=True, filename=None):
        """
        Record audio from microphone
        
        Args:
            output_dir: Directory to save the recording
            device_index: Index of the microphone device to use
            duration: Maximum recording duration in seconds
            auto_stop: Whether to automatically stop on silence
            filename: Custom filename for the recording
        
        Returns:
            Path to the recorded audio file
        """
        max_duration = duration or MAX_RECORDING_DURATION
        frames = []
        
        # If device index is specified, use it
        if device_index is not None:
            try:
                device_info = self.p.get_device_info_by_index(device_index)
                print(f"Using device: {device_info.get('name')}")
            except:
                print(f"Invalid device index: {device_index}, using default")
                device_index = None
        
        # Open microphone stream
        stream = self.p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK)
                        
        print("\nRecording... (speak now)")
        if auto_stop:
            print("Recording will stop automatically after silence is detected")
            print("or press Ctrl+C to stop manually")
        else:
            print(f"Recording for {max_duration} seconds...")
            print("or press Ctrl+C to stop early")
        
        silence_start = None
        start_time = time.time()
        
        try:
            while (time.time() - start_time) < max_duration:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
                
                if auto_stop and self.is_silent(data):
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > MIN_SILENCE_DURATION:
                        print("\nSilence detected, stopping recording")
                        break
                else:
                    silence_start = None
                    
                # Show progress
                elapsed = time.time() - start_time
                if int(elapsed) % 5 == 0:
                    sys.stdout.write(f"\rRecording: {int(elapsed)}s / {max_duration}s")
                    sys.stdout.flush()
                    
        except KeyboardInterrupt:
            print("\nRecording stopped by user")
        finally:
            sys.stdout.write("\n")
            stream.stop_stream()
            stream.close()
            
        # Check if any audio was recorded
        if len(frames) < 5:  # Very short recording, probably just background noise
            print("No speech detected. Please try again.")
            return None
            
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Create a filename with timestamp if none is provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            
        output_path = os.path.join(output_dir, filename)
        
        # Save the recording
        wf = wave.open(output_path, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(frames))
        wf.close()
        
        duration = time.time() - start_time
        print(f"Recording saved to {output_path} ({duration:.2f} seconds)")
        
        return output_path
    
    def play_audio(self, file_path):
        """Play an audio file"""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
            
        try:
            wf = wave.open(file_path, 'rb')
            
            # Open stream
            stream = self.p.open(format=self.p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            
            print(f"Playing {file_path}...")
            
            # Read and play data
            data = wf.readframes(CHUNK)
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(CHUNK)
                
            stream.stop_stream()
            stream.close()
            
            print("Playback complete")
            return True
            
        except Exception as e:
            print(f"Error playing audio: {e}")
            return False
    
    def analyze_audio(self, file_path):
        """Analyze an audio file for metrics"""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return
            
        try:
            wf = wave.open(file_path, 'rb')
            
            # Get basic info
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            duration = n_frames / sample_rate
            
            print(f"\nAudio Analysis: {os.path.basename(file_path)}")
            print("-" * 50)
            print(f"Duration: {duration:.2f} seconds")
            print(f"Channels: {channels}")
            print(f"Sample Rate: {sample_rate} Hz")
            print(f"Sample Width: {sample_width * 8} bits")
            print(f"Total Frames: {n_frames}")
            
            # Read all frames
            wf.rewind()
            frames = wf.readframes(n_frames)
            
            # Convert to numpy array
            data = np.frombuffer(frames, dtype=np.int16)
            
            # Calculate metrics
            max_amplitude = np.max(np.abs(data))
            min_amplitude = np.min(np.abs(data))
            mean_amplitude = np.mean(np.abs(data))
            rms = np.sqrt(np.mean(np.square(data)))
            
            max_db = 20 * np.log10(max_amplitude / 32767) if max_amplitude > 0 else -float('inf')
            mean_db = 20 * np.log10(mean_amplitude / 32767) if mean_amplitude > 0 else -float('inf')
            rms_db = 20 * np.log10(rms / 32767) if rms > 0 else -float('inf')
            
            print("\nAudio Metrics:")
            print(f"Max Amplitude: {max_amplitude} ({max_db:.2f} dB)")
            print(f"Min Amplitude: {min_amplitude}")
            print(f"Mean Amplitude: {mean_amplitude:.2f} ({mean_db:.2f} dB)")
            print(f"RMS Amplitude: {rms:.2f} ({rms_db:.2f} dB)")
            
            # Check for clipping
            clipping_threshold = 32700  # Close to max int16 value
            clipping_samples = np.sum(np.abs(data) > clipping_threshold)
            if clipping_samples > 0:
                clipping_percent = (clipping_samples / len(data)) * 100
                print(f"\n⚠️ Clipping detected: {clipping_samples} samples ({clipping_percent:.2f}%)")
            else:
                print("\n✅ No clipping detected")
                
            # Check for silence
            silence_threshold = 500  # Same as recording threshold
            silence_samples = np.sum(np.abs(data) < silence_threshold)
            silence_percent = (silence_samples / len(data)) * 100
            print(f"Silence: {silence_percent:.2f}% of recording")
            
            # Quality assessment
            if max_db > -1:
                print("\n⚠️ Audio may be too loud - consider reducing microphone gain")
            elif max_db < -20:
                print("\n⚠️ Audio may be too quiet - consider increasing microphone gain")
            else:
                print("\n✅ Audio level is good")
                
            if silence_percent > 50:
                print("⚠️ Recording contains a lot of silence")
            
            # Compare to system threshold
            print(f"\nCurrent silence threshold: {SILENCE_THRESHOLD}")
            if mean_amplitude < SILENCE_THRESHOLD * 2:
                print("⚠️ Microphone signal is weak compared to silence threshold")
                print("   Consider increasing microphone gain or lowering the silence threshold")
            
        except Exception as e:
            print(f"Error analyzing audio: {e}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Microphone Testing Tool")
    parser.add_argument("--list", action="store_true", help="List available microphone devices")
    parser.add_argument("--record", action="store_true", help="Record audio from microphone")
    parser.add_argument("--play", help="Play an audio file")
    parser.add_argument("--analyze", help="Analyze an audio file")
    parser.add_argument("--device", type=int, help="Microphone device index to use")
    parser.add_argument("--duration", type=int, default=MAX_RECORDING_DURATION, 
                      help="Maximum recording duration in seconds")
    parser.add_argument("--output", default=".", help="Output directory for recordings")
    parser.add_argument("--no-auto-stop", action="store_true", 
                      help="Don't stop recording automatically on silence")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = MicrophoneTester()
    
    # Create output directory
    output_dir = args.output
    if output_dir == ".":
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
    
    # Run requested action
    if args.list:
        tester.list_devices()
        
    elif args.record:
        recording_path = tester.record_audio(
            output_dir=output_dir,
            device_index=args.device,
            duration=args.duration,
            auto_stop=not args.no_auto_stop
        )
        if recording_path:
            # Ask if user wants to play back the recording
            play_back = input("\nPlay back the recording? (y/n): ").lower()
            if play_back == 'y':
                tester.play_audio(recording_path)
                
            # Ask if user wants to analyze the recording
            analyze_recording = input("\nAnalyze the recording? (y/n): ").lower()
            if analyze_recording == 'y':
                tester.analyze_audio(recording_path)
                
    elif args.play:
        tester.play_audio(args.play)
        
    elif args.analyze:
        tester.analyze_audio(args.analyze)
        
    else:
        # Interactive mode
        print("==== Microphone Testing Tool ====\n")
        
        while True:
            print("\nAvailable actions:")
            print("1. List microphone devices")
            print("2. Record audio")
            print("3. Play audio file")
            print("4. Analyze audio file")
            print("5. Exit")
            
            choice = input("\nEnter choice (1-5): ")
            
            if choice == '1':
                tester.list_devices()
                
            elif choice == '2':
                # Ask for device
                devices = tester.list_devices()
                device_input = input("\nEnter device index (or press Enter for default): ")
                device_index = None
                if device_input.strip():
                    try:
                        device_index = int(device_input)
                    except ValueError:
                        print("Invalid device index, using default")
                
                # Ask for duration
                duration_input = input(f"\nEnter max duration in seconds (or press Enter for default {MAX_RECORDING_DURATION}s): ")
                duration = MAX_RECORDING_DURATION
                if duration_input.strip():
                    try:
                        duration = int(duration_input)
                    except ValueError:
                        print(f"Invalid duration, using default {MAX_RECORDING_DURATION}s")
                
                # Ask for auto-stop
                auto_stop_input = input("\nEnable auto-stop on silence? (y/n, default: y): ").lower()
                auto_stop = auto_stop_input != 'n'
                
                # Record audio
                recording_path = tester.record_audio(
                    output_dir=output_dir,
                    device_index=device_index,
                    duration=duration,
                    auto_stop=auto_stop
                )
                
                if recording_path:
                    # Ask if user wants to play back the recording
                    play_back = input("\nPlay back the recording? (y/n): ").lower()
                    if play_back == 'y':
                        tester.play_audio(recording_path)
                        
                    # Ask if user wants to analyze the recording
                    analyze_recording = input("\nAnalyze the recording? (y/n): ").lower()
                    if analyze_recording == 'y':
                        tester.analyze_audio(recording_path)
                
            elif choice == '3':
                # Ask for file path
                file_path = input("\nEnter path to audio file: ")
                if file_path:
                    tester.play_audio(file_path)
                else:
                    print("No file specified")
                
            elif choice == '4':
                # Ask for file path
                file_path = input("\nEnter path to audio file for analysis: ")
                if file_path:
                    tester.analyze_audio(file_path)
                else:
                    print("No file specified")
                
            elif choice == '5':
                print("\nExiting...")
                break
                
            else:
                print("\nInvalid choice. Please enter a number from 1-5.")

if __name__ == "__main__":
    main()
