#!/usr/bin/env python3
"""Test script to reproduce the 'Hi!' greeting issue"""

import sys
import logging
from agent import voice_agent

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_hi_greeting():
    """Test that the agent responds to 'Hi!' properly"""
    user_id = "test_user_hi"
    session_id = "test_session_hi"
    
    print("\n" + "="*60)
    print("Testing 'Hi!' greeting...")
    print("="*60 + "\n")
    
    response = voice_agent.process_message(user_id, session_id, "Hi!", region="UK")
    
    print("\n" + "="*60)
    print("RESPONSE:")
    print("="*60)
    print(response)
    print("="*60 + "\n")
    
    # Check if we got the error message
    if "I processed the request but have no response" in response:
        print("❌ ERROR: Got empty response message")
        return False
    else:
        print("✅ SUCCESS: Got a proper response")
        return True

if __name__ == "__main__":
    success = test_hi_greeting()
    sys.exit(0 if success else 1)
