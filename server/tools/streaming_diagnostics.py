"""
Streaming Diagnostics Tool for VR Interview System.

This utility helps diagnose issues with the streaming audio pipeline by:
1. Testing AllTalk server connectivity
2. Validating streaming URL parameters
3. Checking file permissions and access
4. Monitoring file creation and availability
5. Testing audio file retrieval with different strategies

Usage:
  python streaming_diagnostics.py --alltalk_url http://127.0.0.1:7851 --voice "voice_file.wav" --text "Test text"

Additional options:
  --alltalk_dir          Path to AllTalk directory (default: D:/AllTalk/alltalk_tts)
  --verbose              Enable verbose logging
  --test_all             Run all diagnostic tests
  --save_results         Save diagnostic results to a file
"""

import argparse
import asyncio
import aiohttp
import aiofiles
import datetime
import json
import logging
import os
import re
import requests
import sys
import time
import urllib.parse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("streaming_diagnostics")

class StreamingDiagnostics:
    """Diagnostics tool for streaming audio in VR Interview System"""
    
    def __init__(self, alltalk_url, alltalk_dir, voice, verbose=False):
        """Initialize the diagnostics tool"""
        self.alltalk_url = alltalk_url.rstrip('/')
        self.alltalk_dir = alltalk_dir
        self.voice = voice
        self.outputs_dir = os.path.join(alltalk_dir, "outputs")
        self.verbose = verbose
        
        if verbose:
            logger.setLevel(logging.DEBUG)
        
        logger.info(f"Initializing diagnostics with URL: {alltalk_url}")
        logger.info(f"AllTalk directory: {alltalk_dir}")
        logger.info(f"Voice: {voice}")
        
        # Create results dictionary
        self.results = {
            "timestamp": datetime.datetime.now().isoformat(),
            "configuration": {
                "alltalk_url": alltalk_url,
                "alltalk_dir": alltalk_dir,
                "voice": voice
            },
            "tests": {},
            "summary": {
                "success": 0,
                "warning": 0,
                "failure": 0
            }
        }

    async def run_all_tests(self, text="This is a test of the streaming audio system."):
        """Run all diagnostic tests"""
        logger.info("====== STARTING DIAGNOSTIC TESTS ======")
        
        # Test server connectivity
        await self.test_server_connectivity()
        
        # Test basic API endpoints
        await self.test_alltalk_api_endpoints()
        
        # Test directory permissions
        await self.test_directory_permissions()
        
        # Test file generation and retrieval
        await self.test_file_generation_retrieval(text)
        
        # Test streaming URL generation and validation
        await self.test_streaming_url(text)
        
        # Print summary
        self.print_summary()
        
        logger.info("====== DIAGNOSTIC TESTS COMPLETE ======")
        
        return self.results
    
    async def test_server_connectivity(self):
        """Test connectivity to the AllTalk server"""
        logger.info("Testing AllTalk server connectivity...")
        test_name = "server_connectivity"
        
        try:
            # Test basic connectivity with timeout
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.alltalk_url}/api/ready", timeout=5) as response:
                    status = response.status
                    response_time = time.time() - start_time
                    
                    if status == 200:
                        logger.info(f"✅ Server is responding (status: {status}, time: {response_time:.2f}s)")
                        self.record_result(test_name, "success", {
                            "status": status,
                            "response_time": response_time
                        })
                    else:
                        logger.warning(f"⚠️ Server responded with non-200 status: {status}")
                        self.record_result(test_name, "warning", {
                            "status": status,
                            "response_time": response_time
                        })
        except asyncio.TimeoutError:
            logger.error("❌ Connection to AllTalk server timed out")
            self.record_result(test_name, "failure", {
                "error": "Connection timeout",
                "message": "Server did not respond within 5 seconds"
            })
        except Exception as e:
            logger.error(f"❌ Error connecting to AllTalk server: {e}")
            self.record_result(test_name, "failure", {
                "error": str(e),
                "type": type(e).__name__
            })
    
    async def test_alltalk_api_endpoints(self):
        """Test AllTalk API endpoints"""
        logger.info("Testing AllTalk API endpoints...")
        test_name = "api_endpoints"
        results = {}
        
        endpoints = [
            "/api/ready",
            "/api/voices",
            "/api/currentsettings"
        ]
        
        success_count = 0
        async with aiohttp.ClientSession() as session:
            for endpoint in endpoints:
                try:
                    url = f"{self.alltalk_url}{endpoint}"
                    logger.debug(f"Testing endpoint: {url}")
                    
                    start_time = time.time()
                    async with session.get(url, timeout=5) as response:
                        status = response.status
                        response_time = time.time() - start_time
                        
                        if status == 200:
                            logger.info(f"✅ Endpoint {endpoint} OK (time: {response_time:.2f}s)")
                            results[endpoint] = {
                                "status": status,
                                "response_time": response_time,
                                "result": "success"
                            }
                            success_count += 1
                            
                            # For voices endpoint, check if our voice is available
                            if endpoint == "/api/voices":
                                try:
                                    response_json = await response.json()
                                    voices = response_json.get("voices", [])
                                    if self.voice in voices:
                                        logger.info(f"✅ Voice '{self.voice}' found in available voices")
                                        results["voice_available"] = True
                                    else:
                                        logger.warning(f"⚠️ Voice '{self.voice}' NOT found in available voices")
                                        results["voice_available"] = False
                                except Exception as e:
                                    logger.warning(f"⚠️ Could not parse voices response: {e}")
                            
                        else:
                            logger.warning(f"⚠️ Endpoint {endpoint} returned status {status}")
                            results[endpoint] = {
                                "status": status,
                                "response_time": response_time,
                                "result": "warning"
                            }
                except Exception as e:
                    logger.error(f"❌ Error testing endpoint {endpoint}: {e}")
                    results[endpoint] = {
                        "error": str(e),
                        "result": "failure"
                    }
        
        # Record overall result
        if success_count == len(endpoints):
            logger.info("✅ All API endpoints tested successfully")
            self.record_result(test_name, "success", results)
        elif success_count > 0:
            logger.warning(f"⚠️ {success_count}/{len(endpoints)} API endpoints tested successfully")
            self.record_result(test_name, "warning", results)
        else:
            logger.error("❌ All API endpoint tests failed")
            self.record_result(test_name, "failure", results)
    
    async def test_directory_permissions(self):
        """Test directory permissions"""
        logger.info("Testing directory permissions...")
        test_name = "directory_permissions"
        results = {}
        
        # Check if directories exist
        dirs_to_check = [
            self.alltalk_dir,
            self.outputs_dir
        ]
        
        all_passed = True
        for dir_path in dirs_to_check:
            # Check if directory exists
            dir_exists = os.path.exists(dir_path)
            results[f"{dir_path}_exists"] = dir_exists
            
            if dir_exists:
                logger.info(f"✅ Directory exists: {dir_path}")
                
                # Check read permission
                try:
                    files = os.listdir(dir_path)
                    results[f"{dir_path}_readable"] = True
                    logger.info(f"✅ Directory is readable: {dir_path} ({len(files)} files)")
                    
                    # List files for outputs directory
                    if dir_path == self.outputs_dir and self.verbose:
                        for file in files[:10]:  # Show only first 10 files
                            logger.debug(f"File: {file}")
                        if len(files) > 10:
                            logger.debug(f"... and {len(files) - 10} more files")
                        
                except Exception as e:
                    results[f"{dir_path}_readable"] = False
                    logger.error(f"❌ Cannot read directory {dir_path}: {e}")
                    all_passed = False
                
                # Check write permission
                try:
                    test_file = os.path.join(dir_path, f"test_write_{int(time.time())}.tmp")
                    with open(test_file, "w") as f:
                        f.write("Test write permission")
                    results[f"{dir_path}_writable"] = True
                    logger.info(f"✅ Directory is writable: {dir_path}")
                    
                    # Clean up test file
                    os.remove(test_file)
                    results[f"{dir_path}_deletable"] = True
                    logger.info(f"✅ Directory allows file deletion: {dir_path}")
                    
                except Exception as e:
                    results[f"{dir_path}_writable"] = False
                    logger.error(f"❌ Cannot write to directory {dir_path}: {e}")
                    all_passed = False
            else:
                logger.error(f"❌ Directory does not exist: {dir_path}")
                all_passed = False
                
                # Try to create directory
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    logger.info(f"✅ Successfully created directory: {dir_path}")
                    results[f"{dir_path}_created"] = True
                except Exception as e:
                    logger.error(f"❌ Failed to create directory {dir_path}: {e}")
                    results[f"{dir_path}_created"] = False
                    all_passed = False
        
        # Record overall result
        if all_passed:
            logger.info("✅ All directory permission tests passed")
            self.record_result(test_name, "success", results)
        else:
            logger.error("❌ Some directory permission tests failed")
            self.record_result(test_name, "failure", results)
    
    async def test_file_generation_retrieval(self, text):
        """Test file generation and retrieval"""
        logger.info("Testing audio file generation and retrieval...")
        test_name = "file_generation_retrieval"
        results = {}
        
        # Generate unique output filename
        timestamp = int(time.time())
        output_file = f"diag_test_{timestamp}"
        output_path = os.path.join(self.outputs_dir, f"{output_file}.wav")
        
        logger.info(f"Generating audio file with text: '{text[:30]}...'")
        
        try:
            # Make a request to generate audio file
            params = {
                "text": text,
                "voice": self.voice,
                "language": "en",
                "output_file": output_file
            }
            
            start_time = time.time()
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.alltalk_url}/api/tts-generate-streaming",
                    data=params,
                    timeout=30
                ) as response:
                    status = response.status
                    generation_time = time.time() - start_time
                    
                    results["generation_request"] = {
                        "status": status,
                        "time": generation_time,
                        "output_file": output_file
                    }
                    
                    if status == 200:
                        logger.info(f"✅ Audio generation request successful (time: {generation_time:.2f}s)")
                        
                        # Now check if file was actually created
                        # Wait for file to be generated (it may take a moment)
                        logger.info("Waiting for file to be generated...")
                        file_found = False
                        max_wait_time = 30.0  # seconds
                        wait_start = time.time()
                        
                        # List of possible file patterns to check
                        file_patterns = [
                            f"{output_file}.wav",
                            f"{output_file}.wav.wav",
                            output_file
                        ]
                        
                        file_path = None
                        while not file_found and (time.time() - wait_start) < max_wait_time:
                            # Check for file existence with different patterns
                            for pattern in file_patterns:
                                path_to_check = os.path.join(self.outputs_dir, pattern)
                                if os.path.exists(path_to_check):
                                    file_path = path_to_check
                                    file_found = True
                                    logger.info(f"✅ File found: {file_path}")
                                    break
                            
                            if not file_found:
                                # Check for similar files
                                try:
                                    files = os.listdir(self.outputs_dir)
                                    similar_files = [f for f in files if output_file in f]
                                    if similar_files:
                                        file_path = os.path.join(self.outputs_dir, similar_files[0])
                                        file_found = True
                                        logger.info(f"✅ Similar file found: {file_path}")
                                        break
                                except Exception as e:
                                    logger.warning(f"⚠️ Error listing directory: {e}")
                            
                            if not file_found:
                                await asyncio.sleep(1.0)
                        
                        # Record file search results
                        results["file_search"] = {
                            "found": file_found,
                            "search_time": time.time() - wait_start,
                            "file_path": file_path
                        }
                        
                        if file_found:
                            # Check file properties
                            file_size = os.path.getsize(file_path)
                            file_age = time.time() - os.path.getmtime(file_path)
                            
                            results["file_properties"] = {
                                "size": file_size,
                                "age_seconds": file_age
                            }
                            
                            logger.info(f"✅ File properties: size={file_size} bytes, age={file_age:.2f}s")
                            
                            # Valid audio files are typically at least a few KB
                            if file_size < 1000:
                                logger.warning(f"⚠️ File size is suspiciously small: {file_size} bytes")
                            
                            # Try to read the file
                            try:
                                with open(file_path, "rb") as f:
                                    audio_data = f.read(1024)  # Read first 1KB to check header
                                
                                # Basic check for WAV header
                                is_wav = audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]
                                results["file_content"] = {
                                    "readable": True,
                                    "is_wav": is_wav
                                }
                                
                                if is_wav:
                                    logger.info("✅ File contains valid WAV header")
                                else:
                                    logger.warning("⚠️ File does not appear to be a valid WAV file")
                            except Exception as e:
                                logger.error(f"❌ Error reading file {file_path}: {e}")
                                results["file_content"] = {
                                    "readable": False,
                                    "error": str(e)
                                }
                        else:
                            logger.error(f"❌ File not found after {max_wait_time} seconds")
                    else:
                        logger.error(f"❌ Audio generation request failed: status {status}")
        except Exception as e:
            logger.error(f"❌ Error in audio generation test: {e}")
            results["generation_error"] = str(e)
            self.record_result(test_name, "failure", results)
            return
        
        # Determine overall result
        if results.get("file_search", {}).get("found", False) and results.get("file_content", {}).get("readable", False):
            logger.info("✅ Audio file generation and retrieval successful")
            self.record_result(test_name, "success", results)
        elif results.get("file_search", {}).get("found", False):
            logger.warning("⚠️ Audio file was generated but might have issues")
            self.record_result(test_name, "warning", results)
        else:
            logger.error("❌ Audio file generation or retrieval failed")
            self.record_result(test_name, "failure", results)
    
    async def test_streaming_url(self, text):
        """Test streaming URL generation and validation"""
        logger.info("Testing streaming URL generation and validation...")
        test_name = "streaming_url"
        results = {}
        
        # Generate timestamp for unique output file
        timestamp = int(time.time())
        output_file = f"stream_test_{timestamp}"
        
        # 1. Construct streaming URL as our code would
        encoded_text = urllib.parse.quote(text)
        encoded_voice = urllib.parse.quote(self.voice)
        streaming_url = f"{self.alltalk_url}/api/tts-generate-streaming?text={encoded_text}&voice={encoded_voice}&language=en&output_file={output_file}"
        
        # Add timestamp parameter to bypass caching
        streaming_url += f"&_t={timestamp}"
        
        logger.info(f"Generated streaming URL: {streaming_url[:100]}...")
        results["url"] = streaming_url
        
        # 2. Validate URL parameters
        # Check for required parameters
        required_params = ["text", "voice", "language", "output_file"]
        missing_params = []
        
        for param in required_params:
            if f"{param}=" not in streaming_url:
                missing_params.append(param)
        
        if missing_params:
            logger.error(f"❌ Streaming URL missing required parameters: {', '.join(missing_params)}")
            results["missing_params"] = missing_params
            self.record_result(test_name, "failure", results)
            return
        else:
            logger.info("✅ Streaming URL contains all required parameters")
            results["params_check"] = "complete"
        
        # 3. Test access to the streaming URL
        try:
            async with aiohttp.ClientSession() as session:
                # Make a HEAD request first to check if endpoint exists without downloading content
                try:
                    async with session.head(streaming_url, timeout=5) as head_resp:
                        results["head_request"] = {
                            "status": head_resp.status
                        }
                        
                        if head_resp.status == 200:
                            logger.info("✅ Streaming URL endpoint is accessible")
                        else:
                            logger.warning(f"⚠️ Streaming URL HEAD request returned status {head_resp.status}")
                except Exception as e:
                    logger.warning(f"⚠️ HEAD request failed: {e}")
                    results["head_request"] = {
                        "error": str(e)
                    }
                
                # Now test GET request (limited to 10 seconds and 1MB to avoid full download)
                start_time = time.time()
                try:
                    async with session.get(streaming_url, timeout=10) as response:
                        status = response.status
                        response_time = time.time() - start_time
                        
                        # Read first 1MB to check content type
                        chunk = await response.content.read(1024 * 1024)
                        content_type = response.headers.get("Content-Type", "")
                        
                        results["get_request"] = {
                            "status": status,
                            "response_time": response_time,
                            "content_type": content_type,
                            "first_chunk_size": len(chunk)
                        }
                        
                        if status == 200:
                            logger.info(f"✅ Streaming URL GET request successful (time: {response_time:.2f}s)")
                            
                            # Check content type
                            if "audio" in content_type.lower():
                                logger.info(f"✅ Content-Type indicates audio: {content_type}")
                                results["content_check"] = "audio"
                            else:
                                logger.warning(f"⚠️ Content-Type does not indicate audio: {content_type}")
                                results["content_check"] = "non-audio"
                            
                            # Basic check for WAV header in first chunk
                            if chunk.startswith(b'RIFF') and b'WAVE' in chunk[:12]:
                                logger.info("✅ Content contains valid WAV header")
                                results["wav_header"] = True
                            else:
                                logger.warning("⚠️ Content does not appear to be a valid WAV file")
                                results["wav_header"] = False
                        else:
                            logger.error(f"❌ Streaming URL GET request failed: status {status}")
                except asyncio.TimeoutError:
                    logger.warning("⚠️ GET request timed out (this might be expected for streaming)")
                    results["get_request"] = {
                        "timeout": True,
                        "response_time": time.time() - start_time
                    }
                except Exception as e:
                    logger.error(f"❌ GET request error: {e}")
                    results["get_request"] = {
                        "error": str(e)
                    }
        except Exception as e:
            logger.error(f"❌ Error testing streaming URL: {e}")
            results["error"] = str(e)
            self.record_result(test_name, "failure", results)
            return
        
        # Determine overall result based on checks performed
        if results.get("params_check") == "complete" and (
            results.get("wav_header", False) or 
            results.get("content_check") == "audio"
        ):
            logger.info("✅ Streaming URL test successful")
            self.record_result(test_name, "success", results)
        elif results.get("params_check") == "complete" and results.get("get_request", {}).get("status") == 200:
            logger.warning("⚠️ Streaming URL partially working but content may have issues")
            self.record_result(test_name, "warning", results)
        else:
            logger.error("❌ Streaming URL test failed")
            self.record_result(test_name, "failure", results)
    
    def record_result(self, test_name, result, data):
        """Record a test result"""
        self.results["tests"][test_name] = {
            "result": result,
            "data": data
        }
        
        # Update summary
        self.results["summary"][result] += 1
    
    def print_summary(self):
        """Print a summary of test results"""
        summary = self.results["summary"]
        total = sum(summary.values())
        
        logger.info("\n====== TEST SUMMARY ======")
        logger.info(f"Total tests: {total}")
        logger.info(f"✅ Successful: {summary['success']}")
        logger.info(f"⚠️ Warnings: {summary['warning']}")
        logger.info(f"❌ Failures: {summary['failure']}")
        
        # Print failed tests
        failed_tests = [name for name, test in self.results["tests"].items() if test["result"] == "failure"]
        if failed_tests:
            logger.info("\nFailed tests:")
            for test in failed_tests:
                logger.info(f"  - {test}")
    
    def save_results(self, filename=None):
        """Save results to a file"""
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"streaming_diagnostics_{timestamp}.json"
        
        try:
            with open(filename, "w") as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Results saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error saving results: {e}")
            return False

async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Streaming Audio Diagnostics Tool")
    parser.add_argument("--alltalk_url", default="http://127.0.0.1:7851", help="AllTalk server URL")
    parser.add_argument("--alltalk_dir", default="D:/AllTalk/alltalk_tts", help="AllTalk directory")
    parser.add_argument("--voice", default="female_01.wav", help="Voice to use for tests")
    parser.add_argument("--text", default="This is a test of the streaming audio system.", help="Text to use for tests")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--test_all", action="store_true", help="Run all tests")
    parser.add_argument("--save_results", action="store_true", help="Save results to a file")
    parser.add_argument("--output", help="Output filename for results")
    
    args = parser.parse_args()
    
    # Initialize diagnostics
    diagnostics = StreamingDiagnostics(
        alltalk_url=args.alltalk_url,
        alltalk_dir=args.alltalk_dir,
        voice=args.voice,
        verbose=args.verbose
    )
    
    # Run tests
    if args.test_all:
        results = await diagnostics.run_all_tests(args.text)
    else:
        # Run individual tests as specified
        results = {}
        
        # For now, just run all tests if no specific test is specified
        results = await diagnostics.run_all_tests(args.text)
    
    # Save results if requested
    if args.save_results:
        diagnostics.save_results(args.output)

if __name__ == "__main__":
    asyncio.run(main())
