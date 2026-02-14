#!/usr/bin/env python3
"""Test script to simulate the exact web flow: fresh visit + 'Hi!' button click"""

import sys
import logging
import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_fresh_visit_hi():
    """Simulate a fresh page visit and clicking 'Say Hi!' button"""
    
    print("\n" + "="*60)
    print("Testing FRESH VISIT scenario (like clicking 'Say Hi!' button)")
    print("="*60 + "\n")
    
    # Simulate fresh visit - no session_id
    url = "http://localhost:8001/chat"
    payload = {
        "message": "Hi!",
        "region": "UK"
        # NO session_id - simulating fresh visit
    }
    
    print(f"Sending POST to {url}")
    print(f"Payload: {json.dumps(payload, indent=2)}\n")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n" + "="*60)
            print("RESPONSE DATA:")
            print("="*60)
            print(json.dumps(data, indent=2))
            print("="*60 + "\n")
            
            bot_response = data.get('response', '')
            
            # Check for the error message
            if "I processed the request but have no response" in bot_response:
                print("❌ ERROR: Got empty response message!")
                print(f"Response: {bot_response}")
                return False
            else:
                print("✅ SUCCESS: Got a proper response!")
                print(f"Response: {bot_response}")
                return True
        else:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fresh_visit_hi()
    sys.exit(0 if success else 1)
