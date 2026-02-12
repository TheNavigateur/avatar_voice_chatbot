import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_discovery_flow():
    user_id = "test_user_discovery"
    session_id = "test_session_discovery"
    
    steps = [
        "Hi",
        "Yes, I want to plan a beach holiday.",
        "Relaxing, but maybe some adventure too.",
        "28 degrees please.",
        "A mix of everything!"
    ]
    
    print("\n--- Starting Discovery Flow Test ---")
    for msg in steps:
        print(f"\nUser: {msg}")
        response = voice_agent.process_message(user_id, session_id, msg)
        print(f"Agent: {response}")
        
        # Check for non-restrictive phrasing in any turn
        lower_res = response.lower()
        if "beach clubs" in lower_res and "hiking" in lower_res:
            if any(phrase in lower_res for phrase in ["tell me", "which of", "any of", "what", "options"]):
                print("✅ SUCCESS: Found improved activity questioning!")
            else:
                print("⚠️ NOTE: Found activity question but phrasing could be better.")
        
        if "relaxing" in lower_res and "adventurous" in lower_res and "mix" in lower_res:
            print("✅ SUCCESS: Found improved vibe questioning!")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_discovery_flow()
