"""
Performance benchmark utility for VR Interview System.

This module provides tools for benchmarking system performance across
STT, TTS, and LLM components with GPU monitoring.
"""

import time
import torch
import asyncio
import logging
import numpy as np
import os
import sys
from typing import Dict, Any, Optional

# Add the project root directory to the Python path
# This allows imports from the project modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class PerformanceBenchmark:
    """
    Utility for benchmarking the performance of the VR Interview System.
    Performs tests on STT, TTS, and LLM components with GPU monitoring.
    """
    
    def __init__(self, gpu_monitor=None):
        self.logger = logging.getLogger("benchmark")
        self.gpu_monitor = gpu_monitor
        
        # Check for CUDA
        self.cuda_available = torch.cuda.is_available()
        if self.cuda_available:
            self.logger.info(f"Benchmark will use CUDA: {torch.cuda.get_device_name(0)}")
        else:
            self.logger.warning("CUDA not available, benchmarking on CPU only")
    
    async def run_benchmark(self, stt_service, tts_service, llm_client):
        """Run a comprehensive performance benchmark"""
        self.logger.info("Starting performance benchmark")
        results = {}
        
        # Reset GPU stats if available
        if self.gpu_monitor:
            self.gpu_monitor.reset_peak_memory()
            self.gpu_monitor.clear_cache()
        
        # Sample audio for STT benchmark (5 seconds)
        test_audio = np.zeros(5 * 16000, dtype=np.float32)  # 5 seconds at 16kHz
        
        # Sample text for TTS benchmark
        test_text = "This is a benchmark test for the text to speech system performance with GPU acceleration."
        
        # Sample prompt for LLM benchmark
        test_prompt = "Tell me about your experience with Python programming in approximately three sentences."
        
        # Benchmark STT
        results["stt"] = await self._benchmark_stt(stt_service, test_audio)
        
        # Benchmark TTS
        results["tts"] = await self._benchmark_tts(tts_service, test_text)
        
        # Benchmark LLM
        results["llm"] = await self._benchmark_llm(llm_client, test_prompt)
        
        # Calculate total time
        results["total_time"] = results["stt"]["time"] + results["tts"]["time"] + results["llm"]["time"]
        
        # Log summary
        self.logger.info(f"Benchmark complete:")
        self.logger.info(f"STT: {results['stt']['time']:.2f}s")
        self.logger.info(f"TTS: {results['tts']['time']:.2f}s")
        self.logger.info(f"LLM: {results['llm']['time']:.2f}s")
        self.logger.info(f"Total: {results['total_time']:.2f}s")
        
        return results
    
    async def _benchmark_stt(self, stt_service, test_audio):
        """Benchmark STT performance"""
        self.logger.info("Benchmarking STT performance...")
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("Before STT")
            self.gpu_monitor.reset_peak_memory()
        
        start_time = time.time()
        
        # Run the transcription
        try:
            stt_result = stt_service.transcribe(test_audio)
            success = True
        except Exception as e:
            self.logger.error(f"STT benchmark error: {e}")
            stt_result = str(e)
            success = False
        
        elapsed = time.time() - start_time
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("After STT")
            
        self.logger.info(f"STT processing time: {elapsed:.2f}s")
        
        # Clean up
        if self.cuda_available:
            torch.cuda.empty_cache()
            
        return {
            "time": elapsed,
            "success": success,
            "result": stt_result if success else None,
            "error": None if success else stt_result
        }
    
    async def _benchmark_tts(self, tts_service, test_text):
        """Benchmark TTS performance"""
        self.logger.info("Benchmarking TTS performance...")
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("Before TTS")
            self.gpu_monitor.reset_peak_memory()
        
        start_time = time.time()
        
        # Run the synthesis
        try:
            tts_result = tts_service.synthesize(test_text)
            success = tts_result is not None and len(tts_result) > 1000
        except Exception as e:
            self.logger.error(f"TTS benchmark error: {e}")
            tts_result = None
            success = False
        
        elapsed = time.time() - start_time
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("After TTS")
            
        self.logger.info(f"TTS processing time: {elapsed:.2f}s")
        
        # Clean up
        if self.cuda_available:
            torch.cuda.empty_cache()
            
        return {
            "time": elapsed,
            "success": success,
            "result_size": len(tts_result) if success and tts_result else 0,
            "error": None if success else "TTS synthesis failed"
        }
    
    async def _benchmark_llm(self, llm_client, test_prompt):
        """Benchmark LLM performance"""
        self.logger.info("Benchmarking LLM performance...")
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("Before LLM")
            self.gpu_monitor.reset_peak_memory()
        
        start_time = time.time()
        
        # Run the LLM generation
        try:
            llm_result = llm_client.generate_response(test_prompt, [])
            success = llm_result is not None
        except Exception as e:
            self.logger.error(f"LLM benchmark error: {e}")
            llm_result = None
            success = False
        
        elapsed = time.time() - start_time
        
        if self.gpu_monitor:
            self.gpu_monitor.log_memory_usage("After LLM")
            
        self.logger.info(f"LLM processing time: {elapsed:.2f}s")
        
        # Clean up
        if hasattr(llm_client, 'cleanup_gpu_memory'):
            llm_client.cleanup_gpu_memory()
            
        return {
            "time": elapsed,
            "success": success,
            "result": llm_result if success else None,
            "error": None if success else "LLM generation failed"
        }
        
    def run_benchmark_script(self):
        """Command-line entry point for benchmark"""
        # Add imports needed for standalone use
        import argparse
        import sys
        import json
        
        parser = argparse.ArgumentParser(description="Benchmark VR Interview System performance")
        parser.add_argument('--config', type=str, default='config/config.json', help='Path to config file')
        parser.add_argument('--output', type=str, help='Output file for benchmark results (JSON)')
        args = parser.parse_args()
        
        try:
            # Setup logging
            logging.basicConfig(level=logging.INFO)
            
            # Initialize components
            from app.utils.config import load_config
            config = load_config(args.config)
            
            from services.audio.stt_wrapper import STTService
            from services.audio.tts import TTSService
            from services.llm.Ollama_client import OllamaClient
            
            # Create GPU monitor
            try:
                from services.audio.gpu_monitor import GPUMonitor
                gpu_monitor = GPUMonitor()
            except ImportError:
                self.logger.warning("GPU monitoring not available, proceeding without it")
                gpu_monitor = None
            
            # Initialize components
            stt_service = STTService(config["audio"]["stt_model"])
            
            # Use the consolidated TTSService
            tts_service = TTSService(config={
                "alltalk": config.get("alltalk", {}),
                "gtts": {"language": "en"}
            })
            
            llm_client = OllamaClient(
                config["ollama"]["url"],
                config["ollama"]["model"],
                config["ollama"].get("context_length", 4096),
                config=config["ollama"]
            )
            
            # Run benchmark
            self.logger.info("Running benchmark...")
            
            # Create event loop and run benchmark
            loop = asyncio.get_event_loop()
            results = loop.run_until_complete(self.run_benchmark(stt_service, tts_service, llm_client))
            
            # Save results if output file specified
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results, f, indent=2)
                self.logger.info(f"Benchmark results saved to {args.output}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Benchmark failed: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e)}

if __name__ == "__main__":
    benchmark = PerformanceBenchmark()
    benchmark.run_benchmark_script()