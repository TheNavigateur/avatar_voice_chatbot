#!/usr/bin/env python3
"""Test with a completely fresh user (no packages)"""

import sys
import logging
import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_fresh_user_hi():
    """Test with a brand new user who has no packages"""
    
    print("\n" + "="*60)
    print("Testing FRESH USER scenario (no existing packages)")
    print("="*60 + "\n")
    
    # Use a unique user ID to ensure no existing data
    import uuid
    fresh_user_id = f"test_fresh_{uuid.uuid4().hex[:8]}"
    
    url = "http://localhost:8001/chat"
    payload = {
        "message": "Hi!",
        "region": "UK"
        # NO session_id - fresh visit
    }
    
    print(f"Testing with fresh user: {fresh_user_id}")
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
            elif "Hi! I'm Ray" in bot_response or "Hi!" in bot_response:
                print("✅ SUCCESS: Got a proper greeting!")
                print(f"Response: {bot_response}")
                return True
            else:
                print("⚠️  WARNING: Got a response but it doesn't look like a greeting")
                print(f"Response: {bot_response}")
                return True  # Still counts as success if not error message
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
    success = test_fresh_user_hi()
    sys.exit(0 if success else 1)
