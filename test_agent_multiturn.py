import os
import logging
import time
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.ERROR) # Lower noise
logger = logging.getLogger(__name__)

def test_multi_turn_flow():
    user_id = f"test_user_{int(time.time())}"
    session_id = f"test_sess_{int(time.time())}"
    
    turns = [
        "Hi",
        "I want to go to Tenerife on March 10th for 5 days.",
        "2 people.",
        "A hotel with a pool please.",
        "Let's talk about Day 2. Adventure activities please.",
    ]
    
    for i, user_msg in enumerate(turns):
        print(f"\nUser: {user_msg}")
        response = voice_agent.process_message(user_id, session_id, user_msg)
        print(f"Agent: {response}")
        
    # Final turn to test the fix
    last_turn = "yeah let's do a water park"
    print(f"\nUser: {last_turn}")
    response = voice_agent.process_message(user_id, session_id, last_turn)
    print(f"Agent: {response}")
    
    if "Siam Park" in response and "Aqualand" in response and ("better" in response or "choice" in response):
        print("\n❌ FAILURE: Agent presented a menu.")
    else:
        print("\n✅ SUCCESS: Agent followed the new preference-based logic.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_multi_turn_flow()
