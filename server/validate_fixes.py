"""
Pre-deployment validation script for VR Interview System
This script checks if all components can be imported and initialized successfully
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all critical components can be imported"""
    print("🔍 Testing component imports...")
    
    try:
        # Test configuration loading
        from app.utils.config import load_config
        config = load_config()
        print("✅ Configuration loading: OK")
        
        # Test fixed state manager
        from app.state.manager_fixed import StateManager
        state_manager = StateManager()
        print("✅ Fixed state manager: OK")
        
        # Test fixed Ollama client
        from services.llm.Ollama_client_fixed import OllamaClient
        print("✅ Fixed Ollama client import: OK")
        
        # Test scenario import
        from services.llm.scenarios import job_interview
        print("✅ Job interview scenarios: OK")
        
        # Test other components
        from services.audio.stt_wrapper import STTService
        from services.audio.tts import TTSService
        from app.websocket.server_enhanced_fixed import WebSocketServer
        from app.utils.error_handler import ErrorHandler
        from app.utils.heartbeat import HeartbeatService
        print("✅ Other components: OK")
        
        print("🎉 All imports successful!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_ollama_client():
    """Test Ollama client initialization"""
    print("\n🔍 Testing Ollama client initialization...")
    
    try:
        from services.llm.Ollama_client_fixed import OllamaClient
        
        # Test basic initialization
        client = OllamaClient(
            url="http://localhost:11434",
            model="mistral:latest",
            context_length=8192
        )
        print("✅ Ollama client initialization: OK")
        
        # Test prompt generation
        test_prompt = client._format_prompt(
            "Hello, I'm John Smith", 
            [], 
            "introduction"
        )
        
        if "interviewer" in test_prompt.lower() and "candidate" in test_prompt.lower():
            print("✅ Role definition in prompts: OK")
        else:
            print("⚠️ Role definition might be weak")
            
        return True
        
    except Exception as e:
        print(f"❌ Ollama client test failed: {e}")
        return False

def test_state_manager():
    """Test state manager logic"""
    print("\n🔍 Testing state manager logic...")
    
    try:
        from app.state.manager_fixed import StateManager
        
        manager = StateManager()
        
        # Test valid transitions
        valid_tests = [
            ("IDLE", "LISTENING"),
            ("LISTENING", "PROCESSING_STT"),
            ("PROCESSING_STT", "PROCESSING_LLM"),
            ("PROCESSING_LLM", "PROCESSING_TTS"),
            ("PROCESSING_TTS", "RESPONDING"),
            ("RESPONDING", "WAITING")
        ]
        
        for current, next_state in valid_tests:
            if manager._is_valid_transition(current, next_state):
                print(f"✅ Valid transition: {current} → {next_state}")
            else:
                print(f"❌ Should be valid: {current} → {next_state}")
                return False
        
        # Test invalid transitions (should be blocked)
        invalid_tests = [
            ("PROCESSING_LLM", "PROCESSING_LLM"),  # No self-loops!
            ("PROCESSING_TTS", "PROCESSING_TTS"),  # No self-loops!
            ("RESPONDING", "PROCESSING_STT")       # Can't go backwards
        ]
        
        for current, next_state in invalid_tests:
            if not manager._is_valid_transition(current, next_state):
                print(f"✅ Blocked invalid: {current} → {next_state}")
            else:
                print(f"❌ Should be blocked: {current} → {next_state}")
                return False
        
        print("✅ State transition logic: OK")
        return True
        
    except Exception as e:
        print(f"❌ State manager test failed: {e}")
        return False

def main():
    """Run all validation tests"""
    print("🎯 VR Interview System - Pre-deployment Validation")
    print("=" * 50)
    
    success = True
    
    # Test imports
    if not test_imports():
        success = False
    
    # Test Ollama client
    if not test_ollama_client():
        success = False
    
    # Test state manager
    if not test_state_manager():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 ALL TESTS PASSED - System ready for deployment!")
        print("\n🚀 Next steps:")
        print("1. Run: python server_fixed.py")
        print("2. Check startup logs for confirmation messages")
        print("3. Test with Unity client")
        print("4. Monitor for the 3 critical fixes working correctly")
    else:
        print("❌ TESTS FAILED - Please fix issues before deployment")
        
    return success

if __name__ == "__main__":
    main()
