"""
Performance Testing Tool

This script tests and benchmarks the performance of various components
of the VR Interview System, including STT, TTS, and LLM processing.
"""

import sys
import os
import time
import json
import logging
import argparse
import asyncio
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    # Import services
    from services.audio.stt import STTService
    from services.audio.stt_wrapper import STTService as STTWrapper
    from services.audio.tts import TTSService
    from services.audio.alltalk_tts import AllTalkTTSService
    from services.llm.ollama_client import OllamaClient
except ImportError:
    print("Error: Could not import services. Make sure you're running from the project root.")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("performance_test")

class PerformanceTester:
    """Tests performance of VR Interview System components"""
    
    def __init__(self, config_path=None):
        """Initialize the tester with config file"""
        self.config_path = config_path
        
        # Find config file if not specified
        if not self.config_path:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            enhanced_config = os.path.join(project_root, "config_enhanced.json")
            default_config = os.path.join(project_root, "config.json")
            
            if os.path.exists(enhanced_config):
                self.config_path = enhanced_config
            elif os.path.exists(default_config):
                self.config_path = default_config
                
        # Load configuration
        self.config = self._load_config()
        
        # Initialize services
        self.stt_service = None
        self.stt_wrapper = None
        self.tts_service = None
        self.alltalk_service = None
        self.llm_client = None
    
    def _load_config(self):
        """Load configuration from file"""
        if not self.config_path or not os.path.exists(self.config_path):
            print(f"❌ Config file not found: {self.config_path}")
            # Return a basic default config
            return {
                "audio": {
                    "stt_model": "medium",
                    "tts_model": "en"
                },
                "ollama": {
                    "url": "http://localhost:11434",
                    "model": "phi",
                    "context_length": 4096
                }
            }
            
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
                print(f"✅ Loaded configuration from {self.config_path}")
                return config
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return {}
    
    def initialize_stt(self):
        """Initialize STT services"""
        print("\
=== Initializing STT Services ===")
        stt_model = self.config.get("audio", {}).get("stt_model", "medium")
        
        # Initialize both STT services
        start_time = time.time()
        try:
            self.stt_service = STTService(stt_model)
            direct_time = time.time() - start_time
            print(f"✅ STT service initialized in {direct_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to initialize STT service: {e}")
            
        start_time = time.time()
        try:
            self.stt_wrapper = STTWrapper(stt_model)
            wrapper_time = time.time() - start_time
            print(f"✅ STT wrapper initialized in {wrapper_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to initialize STT wrapper: {e}")
            
        # Try to preload the model
        if self.stt_service and hasattr(self.stt_service, '_load_model'):
            try:
                print("Preloading STT model...")
                start_time = time.time()
                self.stt_service._load_model()
                preload_time = time.time() - start_time
                print(f"✅ STT model preloaded in {preload_time:.2f}s")
            except Exception as e:
                print(f"❌ Failed to preload STT model: {e}")
        
        return (self.stt_service is not None) or (self.stt_wrapper is not None)
    
    def initialize_tts(self):
        """Initialize TTS services"""
        print("\
=== Initializing TTS Services ===")
        tts_model = self.config.get("audio", {}).get("tts_model", "en")
        
        # Initialize standard TTS
        start_time = time.time()
        try:
            self.tts_service = TTSService(tts_model)
            tts_time = time.time() - start_time
            print(f"✅ TTS service initialized in {tts_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to initialize TTS service: {e}")
            
        # Initialize AllTalk if configured
        alltalk_config = self.config.get("alltalk", {})
        if alltalk_config and alltalk_config.get("url"):
            url = alltalk_config.get("url")
            voice = alltalk_config.get("voice", "alloy")
            
            start_time = time.time()
            try:
                self.alltalk_service = AllTalkTTSService(url, voice)
                alltalk_time = time.time() - start_time
                print(f"✅ AllTalk service initialized in {alltalk_time:.2f}s")
            except Exception as e:
                print(f"❌ Failed to initialize AllTalk service: {e}")
        
        return (self.tts_service is not None) or (self.alltalk_service is not None)
    
    def initialize_llm(self):
        """Initialize LLM client"""
        print("\
=== Initializing LLM Client ===")
        ollama_config = self.config.get("ollama", {})
        url = ollama_config.get("url", "http://localhost:11434")
        model = ollama_config.get("model", "phi")
        context_length = ollama_config.get("context_length", 4096)
        
        start_time = time.time()
        try:
            self.llm_client = OllamaClient(url, model, context_length, config=ollama_config)
            llm_time = time.time() - start_time
            print(f"✅ LLM client initialized in {llm_time:.2f}s")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize LLM client: {e}")
            return False
    
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
            return audio_data
            
        except Exception as e:
            print(f"Error loading audio file: {e}")
            return None
    
    async def benchmark_stt(self, audio_files, iterations=3):
        """Benchmark STT performance"""
        print("\
=== Benchmarking STT Performance ===")
        
        if not self.stt_service and not self.stt_wrapper:
            print("❌ No STT services initialized")
            return None
            
        # Load audio files
        loaded_files = []
        for file_path in audio_files:
            audio_data = self.load_audio_file(file_path)
            if audio_data:
                loaded_files.append((os.path.basename(file_path), audio_data))
        
        if not loaded_files:
            print("❌ No audio files loaded")
            return None
            
        results = {
            "direct": {},
            "wrapper": {}
        }
        
        # Benchmark each service
        print(f"\
Running STT benchmarks with {iterations} iterations...")
        
        # Direct STT service
        if self.stt_service:
            print("\
--- Direct STT Service ---")
            for filename, audio_data in loaded_files:
                print(f"\
Benchmarking file: {filename}")
                times = []
                
                for i in range(iterations):
                    print(f"Iteration {i+1}/{iterations}...", end="", flush=True)
                    start_time = time.time()
                    transcript = self.stt_service.transcribe(audio_data)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    print(f" {elapsed:.2f}s")
                    
                avg_time = np.mean(times)
                results["direct"][filename] = {
                    "times": times,
                    "avg_time": avg_time,
                    "transcript": transcript
                }
                
                print(f"Average time: {avg_time:.2f}s")
                print(f"Transcript: \"{transcript}\"")
        
        # STT Wrapper
        if self.stt_wrapper:
            print("\
--- STT Wrapper ---")
            for filename, audio_data in loaded_files:
                print(f"\
Benchmarking file: {filename}")
                times = []
                
                for i in range(iterations):
                    print(f"Iteration {i+1}/{iterations}...", end="", flush=True)
                    start_time = time.time()
                    transcript = self.stt_wrapper.transcribe(audio_data)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    print(f" {elapsed:.2f}s")
                    
                avg_time = np.mean(times)
                results["wrapper"][filename] = {
                    "times": times,
                    "avg_time": avg_time,
                    "transcript": transcript
                }
                
                print(f"Average time: {avg_time:.2f}s")
                print(f"Transcript: \"{transcript}\"")
        
        # Summary
        print("\
--- STT Benchmark Summary ---")
        
        if results["direct"] and results["wrapper"]:
            direct_times = [r["avg_time"] for r in results["direct"].values()]
            wrapper_times = [r["avg_time"] for r in results["wrapper"].values()]
            
            print(f"Direct service average: {np.mean(direct_times):.2f}s")
            print(f"Wrapper average: {np.mean(wrapper_times):.2f}s")
            
            if np.mean(direct_times) < np.mean(wrapper_times):
                print(f"Direct service is {np.mean(wrapper_times)/np.mean(direct_times):.2f}x faster")
            else:
                print(f"Wrapper is {np.mean(direct_times)/np.mean(wrapper_times):.2f}x faster")
        elif results["direct"]:
            direct_times = [r["avg_time"] for r in results["direct"].values()]
            print(f"Direct service average: {np.mean(direct_times):.2f}s")
        elif results["wrapper"]:
            wrapper_times = [r["avg_time"] for r in results["wrapper"].values()]
            print(f"Wrapper average: {np.mean(wrapper_times):.2f}s")
        
        # Generate chart
        self._generate_stt_chart(results)
        
        return results
    
    async def benchmark_tts(self, text_samples, iterations=3):
        """Benchmark TTS performance"""
        print("\
=== Benchmarking TTS Performance ===")
        
        if not self.tts_service and not self.alltalk_service:
            print("❌ No TTS services initialized")
            return None
            
        results = {
            "standard": {},
            "alltalk": {}
        }
        
        # Benchmark each service
        print(f"\
Running TTS benchmarks with {iterations} iterations...")
        
        # Standard TTS service
        if self.tts_service:
            print("\
--- Standard TTS Service ---")
            for i, text in enumerate(text_samples):
                sample_name = f"sample_{i+1}"
                print(f"\
Benchmarking sample: {sample_name} ({len(text)} chars)")
                times = []
                sizes = []
                
                for j in range(iterations):
                    print(f"Iteration {j+1}/{iterations}...", end="", flush=True)
                    start_time = time.time()
                    audio_data = self.tts_service.synthesize(text)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    sizes.append(len(audio_data) if audio_data else 0)
                    print(f" {elapsed:.2f}s, {len(audio_data) if audio_data else 0} bytes")
                    
                avg_time = np.mean(times)
                avg_size = np.mean(sizes)
                results["standard"][sample_name] = {
                    "text": text,
                    "times": times,
                    "sizes": sizes,
                    "avg_time": avg_time,
                    "avg_size": avg_size
                }
                
                print(f"Average time: {avg_time:.2f}s")
                print(f"Average size: {avg_size:.0f} bytes")
        
        # AllTalk service
        if self.alltalk_service:
            print("\
--- AllTalk TTS Service ---")
            for i, text in enumerate(text_samples):
                sample_name = f"sample_{i+1}"
                print(f"\
Benchmarking sample: {sample_name} ({len(text)} chars)")
                times = []
                sizes = []
                
                for j in range(iterations):
                    print(f"Iteration {j+1}/{iterations}...", end="", flush=True)
                    start_time = time.time()
                    audio_data = await asyncio.to_thread(self.alltalk_service.synthesize, text)
                    elapsed = time.time() - start_time
                    times.append(elapsed)
                    sizes.append(len(audio_data) if audio_data else 0)
                    print(f" {elapsed:.2f}s, {len(audio_data) if audio_data else 0} bytes")
                    
                avg_time = np.mean(times)
                avg_size = np.mean(sizes)
                results["alltalk"][sample_name] = {
                    "text": text,
                    "times": times,
                    "sizes": sizes,
                    "avg_time": avg_time,
                    "avg_size": avg_size
                }
                
                print(f"Average time: {avg_time:.2f}s")
                print(f"Average size: {avg_size:.0f} bytes")
        
        # Summary
        print("\
--- TTS Benchmark Summary ---")
        
        if results["standard"] and results["alltalk"]:
            standard_times = [r["avg_time"] for r in results["standard"].values()]
            alltalk_times = [r["avg_time"] for r in results["alltalk"].values()]
            
            print(f"Standard TTS average: {np.mean(standard_times):.2f}s")
            print(f"AllTalk average: {np.mean(alltalk_times):.2f}s")
            
            if np.mean(standard_times) < np.mean(alltalk_times):
                print(f"Standard TTS is {np.mean(alltalk_times)/np.mean(standard_times):.2f}x faster")
            else:
                print(f"AllTalk is {np.mean(standard_times)/np.mean(alltalk_times):.2f}x faster")
                
            # Compare audio sizes
            standard_sizes = [r["avg_size"] for r in results["standard"].values()]
            alltalk_sizes = [r["avg_size"] for r in results["alltalk"].values()]
            
            print(f"Standard TTS average size: {np.mean(standard_sizes):.0f} bytes")
            print(f"AllTalk average size: {np.mean(alltalk_sizes):.0f} bytes")
        elif results["standard"]:
            standard_times = [r["avg_time"] for r in results["standard"].values()]
            standard_sizes = [r["avg_size"] for r in results["standard"].values()]
            print(f"Standard TTS average: {np.mean(standard_times):.2f}s")
            print(f"Standard TTS average size: {np.mean(standard_sizes):.0f} bytes")
        elif results["alltalk"]:
            alltalk_times = [r["avg_time"] for r in results["alltalk"].values()]
            alltalk_sizes = [r["avg_size"] for r in results["alltalk"].values()]
            print(f"AllTalk average: {np.mean(alltalk_times):.2f}s")
            print(f"AllTalk average size: {np.mean(alltalk_sizes):.0f} bytes")
        
        # Generate chart
        self._generate_tts_chart(results)
        
        return results
    
    async def benchmark_llm(self, prompt_samples, iterations=3):
        """Benchmark LLM performance"""
        print("\
=== Benchmarking LLM Performance ===")
        
        if not self.llm_client:
            print("❌ LLM client not initialized")
            return None
            
        results = {}
        
        # Benchmark LLM
        print(f"\
Running LLM benchmarks with {iterations} iterations...")
        
        for i, prompt in enumerate(prompt_samples):
            sample_name = f"prompt_{i+1}"
            print(f"\
Benchmarking prompt: {sample_name} ({len(prompt)} chars)")
            print(f"Prompt: \"{prompt[:50]}{'...' if len(prompt) > 50 else ''}\"")
            
            times = []
            response_lengths = []
            
            # First run with empty context
            print("\
Testing with empty context:")
            for j in range(iterations):
                print(f"Iteration {j+1}/{iterations}...", end="", flush=True)
                start_time = time.time()
                response = await self.llm_client.generate_response_async(prompt, [])
                elapsed = time.time() - start_time
                times.append(elapsed)
                response_lengths.append(len(response) if response else 0)
                print(f" {elapsed:.2f}s, {len(response) if response else 0} chars")
                
            avg_time = np.mean(times)
            avg_length = np.mean(response_lengths)
            
            results[sample_name] = {
                "prompt": prompt,
                "empty_context": {
                    "times": times,
                    "response_lengths": response_lengths,
                    "avg_time": avg_time,
                    "avg_length": avg_length,
                    "response": response
                }
            }
            
            print(f"Average time (empty context): {avg_time:.2f}s")
            print(f"Average response length: {avg_length:.0f} chars")
            
            # Now test with context
            context = [
                {"role": "system", "content": "You are a job interviewer conducting an interview with the candidate."},
                {"role": "assistant", "content": "Welcome to the interview. Could you tell me about your background?"},
                {"role": "user", "content": "I have 5 years of experience in software engineering."}
            ]
            
            print("\
Testing with context:")
            context_times = []
            context_lengths = []
            
            for j in range(iterations):
                print(f"Iteration {j+1}/{iterations}...", end="", flush=True)
                start_time = time.time()
                response = await self.llm_client.generate_response_async(prompt, context)
                elapsed = time.time() - start_time
                context_times.append(elapsed)
                context_lengths.append(len(response) if response else 0)
                print(f" {elapsed:.2f}s, {len(response) if response else 0} chars")
                
            avg_context_time = np.mean(context_times)
            avg_context_length = np.mean(context_lengths)
            
            results[sample_name]["with_context"] = {
                "times": context_times,
                "response_lengths": context_lengths,
                "avg_time": avg_context_time,
                "avg_length": avg_context_length,
                "response": response
            }
            
            print(f"Average time (with context): {avg_context_time:.2f}s")
            print(f"Average response length: {avg_context_length:.0f} chars")
            
            # Test caching
            print("\
Testing caching performance:")
            cache_time = time.time()
            cache_response = await self.llm_client.generate_response_async(prompt, [])
            cache_elapsed = time.time() - cache_time
            
            results[sample_name]["cache"] = {
                "time": cache_elapsed,
                "response": cache_response
            }
            
            print(f"Cache time: {cache_elapsed:.2f}s")
            
            if cache_elapsed < avg_time * 0.5:
                print(f"✅ Cache is working ({avg_time/cache_elapsed:.2f}x speedup)")
            else:
                print("⚠️ Cache may not be working as expected")
            
            # Test streaming
            print("\
Testing streaming performance:")
            chunks = []
            
            async def stream_callback(chunk):
                chunks.append(chunk)
                
            stream_time = time.time()
            stream_response = await self.llm_client.stream_response(prompt, [], stream_callback)
            stream_elapsed = time.time() - stream_time
            
            results[sample_name]["streaming"] = {
                "time": stream_elapsed,
                "num_chunks": len(chunks),
                "avg_chunk_size": np.mean([len(c) for c in chunks]) if chunks else 0,
                "response": stream_response
            }
            
            print(f"Streaming time: {stream_elapsed:.2f}s")
            print(f"Received {len(chunks)} chunks")
            print(f"Average chunk size: {np.mean([len(c) for c in chunks]):.1f} chars")
            
        # Summary
        print("\
--- LLM Benchmark Summary ---")
        
        empty_times = [r["empty_context"]["avg_time"] for r in results.values()]
        context_times = [r["with_context"]["avg_time"] for r in results.values()]
        
        print(f"Average time (empty context): {np.mean(empty_times):.2f}s")
        print(f"Average time (with context): {np.mean(context_times):.2f}s")
        print(f"Context overhead: {(np.mean(context_times) - np.mean(empty_times)):.2f}s")
        
        # Calculate throughput
        empty_lengths = [r["empty_context"]["avg_length"] for r in results.values()]
        context_lengths = [r["with_context"]["avg_length"] for r in results.values()]
        
        empty_throughput = np.mean(empty_lengths) / np.mean(empty_times)
        context_throughput = np.mean(context_lengths) / np.mean(context_times)
        
        print(f"Throughput (empty context): {empty_throughput:.2f} chars/sec")
        print(f"Throughput (with context): {context_throughput:.2f} chars/sec")
        
        # Check cache performance
        cache_times = [r["cache"]["time"] for r in results.values()]
        
        if np.mean(cache_times) < np.mean(empty_times) * 0.5:
            print(f"✅ Caching provides {np.mean(empty_times)/np.mean(cache_times):.2f}x speedup")
        else:
            print("⚠️ Caching may not be working as expected")
            
        # Generate chart
        self._generate_llm_chart(results)
        
        return results
    
    def _generate_stt_chart(self, results):
        """Generate chart for STT benchmark results"""
        # Only generate chart if matplotlib is available
        try:
            # Create output directory
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Prepare data
            if results["direct"] and results["wrapper"]:
                filenames = list(results["direct"].keys())
                direct_times = [results["direct"][f]["avg_time"] for f in filenames]
                wrapper_times = [results["wrapper"][f]["avg_time"] for f in filenames]
                
                # Plot comparisons
                plt.figure(figsize=(10, 6))
                width = 0.35
                x = np.arange(len(filenames))
                
                plt.bar(x - width/2, direct_times, width, label='Direct STT')
                plt.bar(x + width/2, wrapper_times, width, label='STT Wrapper')
                
                plt.xlabel('Audio Files')
                plt.ylabel('Average Time (seconds)')
                plt.title('STT Performance Comparison')
                plt.xticks(x, filenames, rotation=45, ha='right')
                plt.legend()
                plt.tight_layout()
                
                # Save chart
                output_path = os.path.join(output_dir, f"stt_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\
STT benchmark chart saved to: {output_path}")
            elif results["direct"]:
                # Plot only direct service
                filenames = list(results["direct"].keys())
                direct_times = [results["direct"][f]["avg_time"] for f in filenames]
                
                plt.figure(figsize=(10, 6))
                plt.bar(filenames, direct_times)
                plt.xlabel('Audio Files')
                plt.ylabel('Average Time (seconds)')
                plt.title('Direct STT Performance')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save chart
                output_path = os.path.join(output_dir, f"stt_direct_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\
STT direct benchmark chart saved to: {output_path}")
            elif results["wrapper"]:
                # Plot only wrapper service
                filenames = list(results["wrapper"].keys())
                wrapper_times = [results["wrapper"][f]["avg_time"] for f in filenames]
                
                plt.figure(figsize=(10, 6))
                plt.bar(filenames, wrapper_times)
                plt.xlabel('Audio Files')
                plt.ylabel('Average Time (seconds)')
                plt.title('STT Wrapper Performance')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save chart
                output_path = os.path.join(output_dir, f"stt_wrapper_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\
STT wrapper benchmark chart saved to: {output_path}")
        except Exception as e:
            print(f"\
Error generating STT chart: {e}")
    
    def _generate_tts_chart(self, results):
        """Generate chart for TTS benchmark results"""
        # Only generate chart if matplotlib is available
        try:
            # Create output directory
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Prepare data
            if results["standard"] and results["alltalk"]:
                samples = list(results["standard"].keys())
                standard_times = [results["standard"][s]["avg_time"] for s in samples]
                alltalk_times = [results["alltalk"][s]["avg_time"] for s in samples]
                
                # Plot comparisons for times
                plt.figure(figsize=(10, 6))
                width = 0.35
                x = np.arange(len(samples))
                
                plt.bar(x - width/2, standard_times, width, label='Standard TTS')
                plt.bar(x + width/2, alltalk_times, width, label='AllTalk TTS')
                
                plt.xlabel('Text Samples')
                plt.ylabel('Average Time (seconds)')
                plt.title('TTS Synthesis Time Comparison')
                plt.xticks(x, samples, rotation=45, ha='right')
                plt.legend()
                plt.tight_layout()
                
                # Save time chart
                output_path = os.path.join(output_dir, f"tts_time_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\
TTS time benchmark chart saved to: {output_path}")
                
                # Plot comparisons for audio sizes
                standard_sizes = [results["standard"][s]["avg_size"] for s in samples]
                alltalk_sizes = [results["alltalk"][s]["avg_size"] for s in samples]
                
                plt.figure(figsize=(10, 6))
                
                plt.bar(x - width/2, standard_sizes, width, label='Standard TTS')
                plt.bar(x + width/2, alltalk_sizes, width, label='AllTalk TTS')
                
                plt.xlabel('Text Samples')
                plt.ylabel('Average Size (bytes)')
                plt.title('TTS Audio Size Comparison')
                plt.xticks(x, samples, rotation=45, ha='right')
                plt.legend()
                plt.tight_layout()
                
                # Save size chart
                output_path = os.path.join(output_dir, f"tts_size_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\
TTS size benchmark chart saved to: {output_path}")
            elif results["standard"]:
                # Plot only standard service
                samples = list(results["standard"].keys())
                standard_times = [results["standard"][s]["avg_time"] for s in samples]
              # Plot only standard service
                samples = list(results["standard"].keys())
                standard_times = [results["standard"][s]["avg_time"] for s in samples]
                
                plt.figure(figsize=(10, 6))
                plt.bar(samples, standard_times)
                plt.xlabel('Text Samples')
                plt.ylabel('Average Time (seconds)')
                plt.title('Standard TTS Performance')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save time chart
                output_path = os.path.join(output_dir, f"tts_standard_time_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\nStandard TTS time benchmark chart saved to: {output_path}")
                
                # Plot sizes if available
                standard_sizes = [results["standard"][s]["avg_size"] for s in samples]
                
                plt.figure(figsize=(10, 6))
                plt.bar(samples, standard_sizes)
                plt.xlabel('Text Samples')
                plt.ylabel('Average Size (bytes)')
                plt.title('Standard TTS Audio Size')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save size chart
                output_path = os.path.join(output_dir, f"tts_standard_size_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\nStandard TTS size benchmark chart saved to: {output_path}")
            elif results["alltalk"]:
                # Plot only AllTalk service
                samples = list(results["alltalk"].keys())
                alltalk_times = [results["alltalk"][s]["avg_time"] for s in samples]
                
                plt.figure(figsize=(10, 6))
                plt.bar(samples, alltalk_times)
                plt.xlabel('Text Samples')
                plt.ylabel('Average Time (seconds)')
                plt.title('AllTalk TTS Performance')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save time chart
                output_path = os.path.join(output_dir, f"tts_alltalk_time_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\nAllTalk TTS time benchmark chart saved to: {output_path}")
                
                # Plot sizes if available
                alltalk_sizes = [results["alltalk"][s]["avg_size"] for s in samples]
                
                plt.figure(figsize=(10, 6))
                plt.bar(samples, alltalk_sizes)
                plt.xlabel('Text Samples')
                plt.ylabel('Average Size (bytes)')
                plt.title('AllTalk TTS Audio Size')
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                
                # Save size chart
                output_path = os.path.join(output_dir, f"tts_alltalk_size_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\nAllTalk TTS size benchmark chart saved to: {output_path}")
        except Exception as e:
            print(f"\nError generating TTS chart: {e}")
    
    def _generate_llm_chart(self, results):
        """Generate chart for LLM benchmark results"""
        # Only generate chart if matplotlib is available
        try:
            # Create output directory
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
            os.makedirs(output_dir, exist_ok=True)
            
            # Prepare data for response time comparison
            prompts = list(results.keys())
            empty_times = [results[p]["empty_context"]["avg_time"] for p in prompts]
            context_times = [results[p]["with_context"]["avg_time"] for p in prompts]
            cache_times = [results[p]["cache"]["time"] for p in prompts]
            streaming_times = [results[p]["streaming"]["time"] for p in prompts]
            
            # Plot response times
            plt.figure(figsize=(12, 6))
            x = np.arange(len(prompts))
            width = 0.2
            
            plt.bar(x - width*1.5, empty_times, width, label='Empty Context')
            plt.bar(x - width/2, context_times, width, label='With Context')
            plt.bar(x + width/2, cache_times, width, label='Cache')
            plt.bar(x + width*1.5, streaming_times, width, label='Streaming')
            
            plt.xlabel('Prompts')
            plt.ylabel('Response Time (seconds)')
            plt.title('LLM Response Time Comparison')
            plt.xticks(x, prompts, rotation=45, ha='right')
            plt.legend()
            plt.tight_layout()
            
            # Save response time chart
            output_path = os.path.join(output_dir, f"llm_response_time_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(output_path)
            print(f"\nLLM response time benchmark chart saved to: {output_path}")
            
            # Plot response lengths
            empty_lengths = [results[p]["empty_context"]["avg_length"] for p in prompts]
            context_lengths = [results[p]["with_context"]["avg_length"] for p in prompts]
            
            plt.figure(figsize=(10, 6))
            width = 0.35
            
            plt.bar(x - width/2, empty_lengths, width, label='Empty Context')
            plt.bar(x + width/2, context_lengths, width, label='With Context')
            
            plt.xlabel('Prompts')
            plt.ylabel('Response Length (characters)')
            plt.title('LLM Response Length Comparison')
            plt.xticks(x, prompts, rotation=45, ha='right')
            plt.legend()
            plt.tight_layout()
            
            # Save response length chart
            output_path = os.path.join(output_dir, f"llm_response_length_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(output_path)
            print(f"\nLLM response length benchmark chart saved to: {output_path}")
            
            # Plot throughput
            empty_throughput = [results[p]["empty_context"]["avg_length"] / results[p]["empty_context"]["avg_time"] for p in prompts]
            context_throughput = [results[p]["with_context"]["avg_length"] / results[p]["with_context"]["avg_time"] for p in prompts]
            
            plt.figure(figsize=(10, 6))
            
            plt.bar(x - width/2, empty_throughput, width, label='Empty Context')
            plt.bar(x + width/2, context_throughput, width, label='With Context')
            
            plt.xlabel('Prompts')
            plt.ylabel('Throughput (chars/sec)')
            plt.title('LLM Throughput Comparison')
            plt.xticks(x, prompts, rotation=45, ha='right')
            plt.legend()
            plt.tight_layout()
            
            # Save throughput chart
            output_path = os.path.join(output_dir, f"llm_throughput_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            plt.savefig(output_path)
            print(f"\nLLM throughput benchmark chart saved to: {output_path}")
            
            # Plot streaming chunks info if available
            try:
                num_chunks = [results[p]["streaming"]["num_chunks"] for p in prompts]
                avg_chunk_size = [results[p]["streaming"]["avg_chunk_size"] for p in prompts]
                
                fig, ax1 = plt.subplots(figsize=(10, 6))
                
                color = 'tab:blue'
                ax1.set_xlabel('Prompts')
                ax1.set_ylabel('Number of Chunks', color=color)
                ax1.bar(x - width/4, num_chunks, width/2, color=color)
                ax1.tick_params(axis='y', labelcolor=color)
                
                ax2 = ax1.twinx()
                color = 'tab:red'
                ax2.set_ylabel('Average Chunk Size (chars)', color=color)
                ax2.bar(x + width/4, avg_chunk_size, width/2, color=color)
                ax2.tick_params(axis='y', labelcolor=color)
                
                plt.title('LLM Streaming Metrics')
                plt.xticks(x, prompts, rotation=45, ha='right')
                fig.tight_layout()
                
                # Save streaming chart
                output_path = os.path.join(output_dir, f"llm_streaming_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                plt.savefig(output_path)
                print(f"\nLLM streaming benchmark chart saved to: {output_path}")
            except Exception as e:
                print(f"Error generating streaming chart: {e}")
                
        except Exception as e:
            print(f"\nError generating LLM chart: {e}")
    
    async def run_benchmarks(self, audio_files=None, text_samples=None, prompt_samples=None, iterations=3):
        """Run all benchmarks"""
        print("==== VR Interview System Performance Benchmarks ====")
        print(f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Find audio files if none specified
        if not audio_files:
            # Try to find sample audio files
            tools_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            sample_paths = [
                os.path.join(tools_dir, "output"),
                os.path.join(tools_dir, "samples"),
                os.path.join(os.path.dirname(tools_dir), "data", "audio", "uploads"),
            ]
            
            audio_files = []
            for path in sample_paths:
                if os.path.exists(path):
                    for ext in ['.wav', '.mp3', '.ogg', '.webm']:
                        files = list(Path(path).glob(f'*{ext}'))
                        if files:
                            audio_files.extend([str(f) for f in files[:2]])  # Limit to 2 files per directory
            
            if audio_files:
                print(f"Found {len(audio_files)} sample audio files")
            else:
                print("No sample audio files found")
        
        # Use default text samples if none specified
        if not text_samples:
            text_samples = [
                "Hello, how are you doing today?",
                "I'm interested in learning more about your experience with software development and the projects you've worked on.",
                "Could you tell me about a challenging situation you faced in your previous role and how you handled it? I'm particularly interested in understanding your problem-solving approach.",
                "Thank you for sharing that information. Based on your background, I think you'd be a great fit for our team. Do you have any questions about the position or our company culture that I can answer for you?"
            ]
            print(f"Using {len(text_samples)} default text samples")
        
        # Use default prompt samples if none specified
        if not prompt_samples:
            prompt_samples = [
                "Tell me about your experience with Python.",
                "What challenging project have you worked on recently?",
                "How do you handle conflicts in a team environment?",
                "Describe your approach to solving complex technical problems."
            ]
            print(f"Using {len(prompt_samples)} default prompt samples")
        
        # Initialize services
        print("\n--- Initializing Services ---")
        
        # Initialize STT
        stt_initialized = self.initialize_stt()
        
        # Initialize TTS
        tts_initialized = self.initialize_tts()
        
        # Initialize LLM
        llm_initialized = self.initialize_llm()
        
        # Run benchmarks
        results = {}
        
        # STT benchmark
        if stt_initialized and audio_files:
            print("\n--- Running STT Benchmarks ---")
            stt_results = await self.benchmark_stt(audio_files, iterations)
            results["stt"] = stt_results
        
        # TTS benchmark
        if tts_initialized and text_samples:
            print("\n--- Running TTS Benchmarks ---")
            tts_results = await self.benchmark_tts(text_samples, iterations)
            results["tts"] = tts_results
        
        # LLM benchmark
        if llm_initialized and prompt_samples:
            print("\n--- Running LLM Benchmarks ---")
            llm_results = await self.benchmark_llm(prompt_samples, iterations)
            results["llm"] = llm_results
        
        print("\n==== Performance Benchmark Summary ====")
        if "stt" in results:
            print("✅ STT benchmarks completed")
        else:
            print("❌ STT benchmarks skipped")
            
        if "tts" in results:
            print("✅ TTS benchmarks completed")
        else:
            print("❌ TTS benchmarks skipped")
            
        if "llm" in results:
            print("✅ LLM benchmarks completed")
        else:
            print("❌ LLM benchmarks skipped")
            
        print("\nPerformance benchmarks complete!")
        
        return results
        
    def cleanup(self):
        """Clean up resources"""
        if self.llm_client:
            self.llm_client.cleanup()
            print("Cleaned up LLM client resources")

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Performance Testing Tool")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--audio", help="Directory or file(s) for audio testing", nargs='+')
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations for each test")
    parser.add_argument("--components", choices=["all", "stt", "tts", "llm"], 
                      default="all", help="Component(s) to benchmark")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = PerformanceTester(args.config)
    
    try:
        # Prepare audio files
        audio_files = []
        if args.audio:
            for path in args.audio:
                if os.path.isdir(path):
                    # If it's a directory, find all audio files
                    for ext in ['.wav', '.mp3', '.ogg', '.webm']:
                        files = list(Path(path).glob(f'*{ext}'))
                        audio_files.extend([str(f) for f in files])
                elif os.path.isfile(path):
                    # If it's a file, add it directly
                    audio_files.append(path)
        
        # Run specific component benchmark or all
        if args.components == "stt":
            tester.initialize_stt()
            await tester.benchmark_stt(audio_files or None, args.iterations)
        elif args.components == "tts":
            tester.initialize_tts()
            await tester.benchmark_tts(None, args.iterations)
        elif args.components == "llm":
            tester.initialize_llm()
            await tester.benchmark_llm(None, args.iterations)
        else:
            # Run all benchmarks
            await tester.run_benchmarks(audio_files or None, None, None, args.iterations)
            
    finally:
        # Clean up
        tester.cleanup()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())