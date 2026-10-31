#!/usr/bin/env python3
"""
Ollama LLM Integration Test

This script tests the Ollama API integration, including:
- Connection to Ollama server
- Model availability
- Response generation
- Response caching
- Streaming responses
- Performance metrics
"""

import sys
import os
import time
import json
import logging
import argparse
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    # Import the OllamaClient
    from services.llm.ollama_client import OllamaClient
except ImportError:
    print("Error: Could not import OllamaClient. Make sure you're running from the project root.")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ollama_test")

class OllamaTester:
    """Tests Ollama integration with the VR Interview System"""
    
    def __init__(self, config_path=None):
        """Initialize the tester"""
        self.config = self._load_config(config_path)
        self.client = None
        
    def _load_config(self, config_path):
        """Load configuration from file with fallback to default"""
        if not config_path:
            # Try to find config in parent directory
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 
                                      "config", "config.json")
        
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
            # Return a basic default config
            return {
                "ollama": {
                    "url": "http://localhost:11434",
                    "model": "phi",
                    "context_length": 4096
                }
            }
    
    def initialize_client(self):
        """Initialize the Ollama client"""
        ollama_config = self.config.get("ollama", {})
        url = ollama_config.get("url", "http://localhost:11434")
        model = ollama_config.get("model", "phi")
        context_length = ollama_config.get("context_length", 4096)
        
        logger.info(f"Initializing Ollama client with URL: {url}, model: {model}")
        self.client = OllamaClient(url, model, context_length, config=ollama_config)
        return self.client
    
    async def test_connection(self):
        """Test connection to Ollama server"""
        print("\n=== Testing Ollama Connection ===")
        import requests
        
        url = self.config.get("ollama", {}).get("url", "http://localhost:11434")
        try:
            response = requests.get(f"{url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                print(f"✅ Connected to Ollama server at {url}")
                print(f"Available models: {', '.join([m.get('name', 'unknown') for m in models])}")
                return True
            else:
                print(f"❌ Failed to connect to Ollama: Status code {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Failed to connect to Ollama: {e}")
            print("\nTroubleshooting:")
            print("1. Make sure Ollama is running")
            print("2. Check the URL in config.json")
            print("3. Try running 'ollama list' from command line")
            return False
    
    async def test_basic_response(self):
        """Test a basic response from the LLM"""
        if not self.client:
            print("Initializing client first...")
            self.initialize_client()
            
        print("\n=== Testing Basic Response ===")
        prompt = "What qualities do you look for in a software developer?"
        
        print(f"Prompt: \"{prompt}\"")
        print("Generating response...")
        
        start_time = time.time()
        response = await self.client.generate_response_async(prompt, [])
        elapsed = time.time() - start_time
        
        print(f"\nResponse ({elapsed:.2f}s):")
        print(f"\"{response}\"")
        
        # Basic quality check
        if len(response) < 10:
            print("❌ Response seems too short")
        elif "error" in response.lower():
            print("❌ Response contains error message")
        else:
            print("✅ Response looks good")
            
        return response, elapsed
    
    async def test_streaming(self):
        """Test streaming response"""
        if not self.client:
            print("Initializing client first...")
            self.initialize_client()
            
        print("\n=== Testing Streaming Response ===")
        prompt = "Describe the role of a software architect in three sentences."
        
        print(f"Prompt: \"{prompt}\"")
        print("Streaming response (chunks will appear as received):")
        
        chunks = []
        
        async def stream_callback(chunk):
            chunks.append(chunk)
            print(f"\rReceived: {len(chunks)} chunks, {sum(len(c) for c in chunks)} chars", end="")
        
        start_time = time.time()
        full_response = await self.client.stream_response(prompt, [], stream_callback)
        elapsed = time.time() - start_time
        
        print(f"\n\nFull response ({elapsed:.2f}s):")
        print(f"\"{full_response}\"")
        
        print(f"\nReceived {len(chunks)} chunks over {elapsed:.2f} seconds")
        if chunks:  # Check if chunks list is not empty
            print(f"Average chunk size: {sum(len(c) for c in chunks) / len(chunks):.1f} chars")
        else:
            print("Warning: No chunks received during streaming")
        print(f"Throughput: {len(full_response) / elapsed:.1f} chars/sec")
        
        return full_response, elapsed, chunks
    
    async def test_caching(self):
        """Test response caching"""
        if not self.client:
            print("Initializing client first...")
            self.initialize_client()
            
        print("\n=== Testing Response Caching ===")
        prompt = "What makes a good team leader?"
        
        print(f"Prompt: \"{prompt}\"")
        print("First request (should hit API)...")
        
        # First request
        start_time = time.time()
        response1 = await self.client.generate_response_async(prompt, [])
        elapsed1 = time.time() - start_time
        
        print(f"First response time: {elapsed1:.2f}s")
        
        # Second request - should use cache
        print("\nSecond request with same prompt (should use cache)...")
        start_time = time.time()
        response2 = await self.client.generate_response_async(prompt, [])
        elapsed2 = time.time() - start_time
        
        print(f"Second response time: {elapsed2:.2f}s")
        
        # Cache hit?
        cache_hit = elapsed2 < elapsed1 * 0.5
        
        if cache_hit:
            print(f"✅ Cache appears to be working (speedup: {elapsed1/elapsed2:.1f}x)")
        else:
            print("❌ Cache may not be working as expected")
            
        return {
            "first_time": elapsed1,
            "second_time": elapsed2,
            "speedup": elapsed1/elapsed2 if elapsed2 > 0 else 0,
            "cache_hit": cache_hit
        }
    
    async def test_context_handling(self):
        """Test handling of conversation context"""
        if not self.client:
            print("Initializing client first...")
            self.initialize_client()
            
        print("\n=== Testing Context Handling ===")
        
        # Create a conversation context
        context = [
            {"role": "user", "content": "What qualities do you look for in a developer?"},
            {"role": "assistant", "content": "I look for technical skills, problem-solving ability, communication, teamwork, and a growth mindset."}
        ]
        
        prompt = "Could you elaborate on the importance of communication skills?"
        
        print("Context:")
        for message in context:
            role = message["role"]
            content = message["content"]
            print(f"  {role.capitalize()}: {content}")
            
        print(f"\nPrompt: \"{prompt}\"")
        print("Generating response with context...")
        
        start_time = time.time()
        response = await self.client.generate_response_async(prompt, context)
        elapsed = time.time() - start_time
        
        print(f"\nResponse ({elapsed:.2f}s):")
        print(f"\"{response}\"")
        
        # Check if response references the context
        context_aware = any(
            term in response.lower() 
            for term in ["developer", "technical", "skill", "problem-solving", "teamwork", "mindset"]
        )
        
        if context_aware:
            print("✅ Response appears to use context")
        else:
            print("❓ Response may not be using context effectively")
            
        return response, elapsed, context_aware
    
    async def test_interview_scenario(self):
        """Test an interview-specific scenario"""
        if not self.client:
            print("Initializing client first...")
            self.initialize_client()
            
        print("\n=== Testing Interview Scenario ===")
        
        # System prompt to behave as an interviewer
        system_prompt = self.config.get("ollama", {}).get("system_prompt", 
                         "You are a job interviewer conducting an interview with the candidate. "
                         "Your questions should be relevant to a software engineering position. "
                         "Keep your responses concise and professional.")
        
        # Simulate a short interview conversation
        conversation = [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": "Welcome to the interview. Could you tell me a bit about your background in software development?"},
            {"role": "user", "content": "I've been working as a backend developer for 5 years, primarily with Python and Node.js. I've built several REST APIs and microservices."}
        ]
        
        prompt = "That sounds interesting. Can you tell me about a challenging project you worked on and how you solved the problems you encountered?"
        
        print("Simulating an interview conversation...")
        print(f"Last user input: \"{conversation[-1]['content']}\"")
        print(f"Interviewer prompt: \"{prompt}\"")
        
        start_time = time.time()
        response = await self.client.generate_response_async(prompt, conversation)
        elapsed = time.time() - start_time
        
        print(f"\nInterviewer response ({elapsed:.2f}s):")
        print(f"\"{response}\"")
        
        # Analyze response quality
        is_question = "?" in response
        is_concise = len(response) < 300
        is_relevant = any(term in response.lower() for term in 
                          ["project", "challenge", "problem", "solution", "work", "develop"])
        
        print("\nResponse analysis:")
        print(f"- Contains follow-up question: {'Yes' if is_question else 'No'}")
        print(f"- Concise: {'Yes' if is_concise else 'No'}")
        print(f"- Relevant to prompt: {'Yes' if is_relevant else 'No'}")
        
        score = sum([is_question, is_concise, is_relevant])
        if score >= 2:
            print("✅ Response is suitable for interview scenario")
        else:
            print("⚠️ Response may need improvement for interview scenarios")
            
        return response, elapsed, score
    
    async def run_all_tests(self):
        """Run all tests"""
        print("==== Ollama Integration Test ====")
        print(f"Running tests at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Test connection
        if not await self.test_connection():
            print("\n❌ Connection test failed. Cannot continue with other tests.")
            return False
            
        # Initialize client
        self.initialize_client()
        
        # Run all tests
        try:
            basic_response = await self.test_basic_response()
            streaming = await self.test_streaming()
            caching = await self.test_caching()
            context = await self.test_context_handling()
            interview = await self.test_interview_scenario()
            
            # Summary
            print("\n==== Test Summary ====")
            print(f"Basic response: {basic_response[1]:.2f}s")
            print(f"Streaming response: {streaming[1]:.2f}s, {len(streaming[2])} chunks")
            print(f"Caching: {'Working' if caching['cache_hit'] else 'Not working'}, "
                 f"Speedup: {caching['speedup']:.1f}x")
            print(f"Context handling: {'Using context' if context[2] else 'Not using context effectively'}")
            print(f"Interview scenario: Score {interview[2]}/3")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Error during tests: {e}")
            import traceback
            print(traceback.format_exc())
            return False
    
    def cleanup(self):
        """Clean up resources"""
        if self.client:
            self.client.cleanup()
            print("Cleaned up Ollama client resources")
            

async def main():
    """Main entry point"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Ollama Integration Test")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("--test", choices=["all", "connection", "basic", "streaming", "caching", "context", "interview"],
                        default="all", help="Specific test to run")
    
    args = parser.parse_args()
    
    # Create tester instance
    tester = OllamaTester(args.config)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        # Run selected test
        if args.test == "connection":
            await tester.test_connection()
        elif args.test == "basic":
            await tester.test_basic_response()
        elif args.test == "streaming":
            await tester.test_streaming()
        elif args.test == "caching":
            await tester.test_caching()
        elif args.test == "context":
            await tester.test_context_handling()
        elif args.test == "interview":
            await tester.test_interview_scenario()
        else:
            # Run all tests
            await tester.run_all_tests()
    finally:
        # Clean up
        tester.cleanup()

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())
