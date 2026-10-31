#!/usr/bin/env python3
"""
Transcription Testing Tool

This script tests the speech-to-text (STT) transcription functionality,
evaluating accuracy, speed, and robustness of the Whisper implementation.
"""

import sys
import os
import time
import logging
import argparse
import asyncio
import numpy as np
import wave
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    # Import the STT service
    from services.audio.stt import STTService
    from services.audio.stt_wrapper import STTService as STTWrapper
except ImportError:
    print("Error: Could not import STT services. Make sure you're running from the project root.")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("transcription_test")

class TranscriptionTester:
    """Tests STT transcription functionality"""
    
    def __init__(self, model="medium"):
        """Initialize the tester with specified model size"""
        self.model = model
        self.stt_service = None
        self.stt_wrapper = None
        
    def initialize_services(self):
        """Initialize the STT services"""
        print(f"Initializing STT service with model: {self.model}")
        
        # Try to initialize the direct STT service first
        try:
            start_time = time.time()
            self.stt_service = STTService(self.model)
            init_time = time.time() - start_time
            print(f"✅ STT service initialized in {init_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to initialize STT service: {e}")
            self.stt_service = None
        
        # Then try to initialize the STT wrapper
        try:
            start_time = time.time()
            self.stt_wrapper = STTWrapper(self.model)
            init_time = time.time() - start_time
            print(f"✅ STT wrapper initialized in {init_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to initialize STT wrapper: {e}")
            self.stt_wrapper = None
            
        # Check if either service was initialized
        if not self.stt_service and not self.stt_wrapper:
            print("❌ Failed to initialize any STT service")
            return False
            
        return True
    
    def load_audio_file(self, file_path):
        """Load audio data from file"""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return None
            
        try:
            # Read as binary data
            with open(file_path, 'rb') as f:
                audio_data = f.read()
                
            print(f"Loaded {len(audio_data)} bytes from {file_path}")
            
            # Try to parse with wave module to get info
            try:
                with wave.open(file_path, 'rb') as wf:
                    channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                    sample_rate = wf.getframerate()
                    n_frames = wf.getnframes()
                    duration = n_frames / sample_rate
                    
                    print(f"Audio info: {duration:.2f}s, {channels} channel(s), {sample_rate} Hz, {sample_width*8} bits")
            except Exception as e:
                print(f"Could not parse audio info: {e}")
                
            return audio_data
            
        except Exception as e:
            print(f"Error loading audio file: {e}")
            return None
    
    def transcribe_with_service(self, audio_data):
        """Transcribe using the direct STT service"""
        if not self.stt_service:
            print("STT service not initialized")
            return None, 0
            
        try:
            start_time = time.time()
            transcript = self.stt_service.transcribe(audio_data)
            elapsed = time.time() - start_time
            
            return transcript, elapsed
            
        except Exception as e:
            print(f"Error transcribing with STT service: {e}")
            return None, 0
    
    def transcribe_with_wrapper(self, audio_data):
        """Transcribe using the STT wrapper"""
        if not self.stt_wrapper:
            print("STT wrapper not initialized")
            return None, 0
            
        try:
            start_time = time.time()
            transcript = self.stt_wrapper.transcribe(audio_data)
            elapsed = time.time() - start_time
            
            return transcript, elapsed
            
        except Exception as e:
            print(f"Error transcribing with STT wrapper: {e}")
            return None, 0
    
    def analyze_transcript(self, transcript):
        """Analyze transcript quality"""
        if not transcript:
            print("No transcript to analyze")
            return None
            
        # Basic analysis
        word_count = len(transcript.split())
        char_count = len(transcript)
        sentences = transcript.split('.')
        sentence_count = len([s for s in sentences if s.strip()])
        
        print(f"Analysis:")
        print(f"- Word count: {word_count}")
        print(f"- Character count: {char_count}")
        print(f"- Estimated sentences: {sentence_count}")
        
        # Check for common issues
        issues = []
        
        if word_count == 0:
            issues.append("Empty transcript")
        
        if word_count > 0 and char_count / word_count < 3:
            issues.append("Very short words - possible garbage output")
            
        if any(w.lower() in transcript.lower() for w in ["umm", "uhh", "hmm"]):
            issues.append("Contains filler words")
            
        # Print issues if any
        if issues:
            print("Potential issues detected:")
            for issue in issues:
                print(f"- {issue}")
        else:
            print("No obvious issues detected")
            
        return {
            "word_count": word_count,
            "char_count": char_count,
            "sentence_count": sentence_count,
            "issues": issues
        }
    
    def test_transcription(self, file_path):
        """Test transcription on a single audio file"""
        print(f"\n=== Testing Transcription: {os.path.basename(file_path)} ===")
        
        # Load audio
        audio_data = self.load_audio_file(file_path)
        if not audio_data:
            return None
            
        results = {}
        
        # Transcribe with direct service
        if self.stt_service:
            print("\nTranscribing with direct STT service...")
            transcript, elapsed = self.transcribe_with_service(audio_data)
            
            if transcript:
                print(f"Transcript ({elapsed:.2f}s):")
                print(f"\"{transcript}\"")
                
                print("\nDirect service analysis:")
                analysis = self.analyze_transcript(transcript)
                
                results["direct"] = {
                    "transcript": transcript,
                    "time": elapsed,
                    "analysis": analysis
                }
            else:
                print("❌ Direct service transcription failed")
                
        # Transcribe with wrapper
        if self.stt_wrapper:
            print("\nTranscribing with STT wrapper...")
            transcript, elapsed = self.transcribe_with_wrapper(audio_data)
            
            if transcript:
                print(f"Transcript ({elapsed:.2f}s):")
                print(f"\"{transcript}\"")
                
                print("\nWrapper analysis:")
                analysis = self.analyze_transcript(transcript)
                
                results["wrapper"] = {
                    "transcript": transcript,
                    "time": elapsed,
                    "analysis": analysis
                }
            else:
                print("❌ Wrapper transcription failed")
                
        # Compare results if both services were used
        if "direct" in results and "wrapper" in results:
            direct_time = results["direct"]["time"]
            wrapper_time = results["wrapper"]["time"]
            
            print("\nComparison:")
            print(f"- Direct service: {direct_time:.2f}s")
            print(f"- Wrapper: {wrapper_time:.2f}s")
            
            if direct_time > 0 and wrapper_time > 0:
                if direct_time < wrapper_time:
                    print(f"Direct service was {wrapper_time/direct_time:.1f}x faster")
                else:
                    print(f"Wrapper was {direct_time/wrapper_time:.1f}x faster")
                    
            # Compare transcripts
            direct_transcript = results["direct"]["transcript"]
            wrapper_transcript = results["wrapper"]["transcript"]
            
            if direct_transcript == wrapper_transcript:
                print("Both services produced identical transcripts")
            else:
                print("Services produced different transcripts")
                
                # Simple word-level difference calculation
                direct_words = set(direct_transcript.lower().split())
                wrapper_words = set(wrapper_transcript.lower().split())
                
                common_words = direct_words.intersection(wrapper_words)
                diff_percentage = 100 - (len(common_words) * 200 / (len(direct_words) + len(wrapper_words)))
                
                print(f"Difference: approximately {diff_percentage:.1f}%")
                
        return results
    
    def test_batch(self, directory):
        """Test transcription on a batch of audio files"""
        print(f"\n=== Testing Batch Transcription: {directory} ===")
        
        # Find audio files
        audio_files = []
        for ext in ['.wav', '.mp3', '.ogg', '.webm']:
            audio_files.extend(list(Path(directory).glob(f'*{ext}')))
            
        if not audio_files:
            print(f"No audio files found in {directory}")
            return None
            
        print(f"Found {len(audio_files)} audio files")
        
        # Test each file
        results = {}
        for file_path in audio_files:
            file_result = self.test_transcription(str(file_path))
            if file_result:
                results[file_path.name] = file_result
                
        # Summarize results
        print("\n=== Batch Summary ===")
        
        if "direct" in next(iter(results.values()), {}):
            direct_times = [r["direct"]["time"] for r in results.values() if "direct" in r]
            if direct_times:
                print(f"Direct service average time: {np.mean(direct_times):.2f}s")
                
        if "wrapper" in next(iter(results.values()), {}):
            wrapper_times = [r["wrapper"]["time"] for r in results.values() if "wrapper" in r]
            if wrapper_times:
                print(f"Wrapper average time: {np.mean(wrapper_times):.2f}s")
                
        return results
    
    def preload_model(self):
        """Explicitly preload the model"""
        print("\n=== Preloading Model ===")
        
        if self.stt_service:
            try:
                start_time = time.time()
                # Try to access internal _model attribute if it exists
                if hasattr(self.stt_service, '_load_model'):
                    self.stt_service._load_model()
                    elapsed = time.time() - start_time
                    print(f"✅ Preloaded model in {elapsed:.2f}s")
                    return True
                else:
                    print("❌ STT service does not support explicit preloading")
            except Exception as e:
                print(f"❌ Error preloading model: {e}")
                
        return False
    
    def test_noise_robustness(self, file_path, noise_levels=[0.01, 0.05, 0.1]):
        """Test robustness against noise by adding synthetic noise"""
        print("\n=== Testing Noise Robustness ===")
        
        # Load audio as numpy array
        try:
            with wave.open(file_path, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                audio_np = np.frombuffer(frames, dtype=np.int16)
                
                # Original audio info
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                
        except Exception as e:
            print(f"Error loading audio for noise test: {e}")
            return None
            
        # First get clean transcription
        audio_data = self.load_audio_file(file_path)
        if not audio_data or not self.stt_service:
            return None
            
        clean_transcript, clean_time = self.transcribe_with_service(audio_data)
        print(f"Clean transcript ({clean_time:.2f}s):")
        print(f"\"{clean_transcript}\"")
        
        results = {"clean": {"transcript": clean_transcript, "time": clean_time}}
        output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Test with different noise levels
        for noise_level in noise_levels:
            print(f"\nTesting with noise level: {noise_level:.2f}")
            
            # Create noise
            noise = np.random.normal(0, 32767 * noise_level, size=audio_np.shape).astype(np.int16)
            noisy_audio = np.clip(audio_np + noise, -32768, 32767).astype(np.int16)
            
            # Save noisy audio
            noisy_file = os.path.join(output_dir, f"noisy_{int(noise_level*100)}pct.wav")
            with wave.open(noisy_file, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(sample_width)
                wf.setframerate(sample_rate)
                wf.writeframes(noisy_audio.tobytes())
                
            print(f"Created noisy audio file: {noisy_file}")
            
            # Load and transcribe
            with open(noisy_file, 'rb') as f:
                noisy_audio_data = f.read()
                
            noisy_transcript, noisy_time = self.transcribe_with_service(noisy_audio_data)
            print(f"Noisy transcript ({noisy_time:.2f}s):")
            print(f"\"{noisy_transcript}\"")
            
            # Compare with clean transcript
            if clean_transcript and noisy_transcript:
                clean_words = set(clean_transcript.lower().split())
                noisy_words = set(noisy_transcript.lower().split())
                
                common_words = clean_words.intersection(noisy_words)
                diff_percentage = 100 - (len(common_words) * 200 / (len(clean_words) + len(noisy_words)))
                
                print(f"Difference from clean: approximately {diff_percentage:.1f}%")
                
                results[f"noise_{int(noise_level*100)}pct"] = {
                    "transcript": noisy_transcript,
                    "time": noisy_time,
                    "diff_percentage": diff_percentage
                }
                
        return results

def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcription Testing Tool")
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large"], 
                        default="medium", help="Whisper model size")
    parser.add_argument("--file", help="Audio file to transcribe")
    parser.add_argument("--batch", help="Directory with audio files for batch processing")
    parser.add_argument("--preload", action="store_true", help="Explicitly preload the model")
    parser.add_argument("--noise", action="store_true", help="Test noise robustness")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = TranscriptionTester(args.model)
    
    # Initialize services
    if not tester.initialize_services():
        print("Failed to initialize STT services. Exiting.")
        return 1
    
    # Preload model if requested
    if args.preload:
        tester.preload_model()
    
    # Find test audio if none specified
    if not args.file and not args.batch:
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
                audio_files = []
                for ext in ['.wav', '.mp3', '.ogg', '.webm']:
                    audio_files.extend(list(Path(path).glob(f'*{ext}')))
                
                if audio_files:
                    args.file = str(audio_files[0])
                    print(f"Using sample audio file: {args.file}")
                    found = True
                    break
        
        if not found:
            print("No audio file specified and no samples found.")
            print("Use --file to specify an audio file or --batch for a directory of files.")
            return 1
    
    # Run requested test
    if args.batch:
        tester.test_batch(args.batch)
    elif args.file:
        if args.noise:
            tester.test_noise_robustness(args.file)
        else:
            tester.test_transcription(args.file)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
