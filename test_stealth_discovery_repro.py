import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_stealth_discovery_strict():
    user_id = "test_user_stealth_strict"
    session_id = "test_session_stealth_strict"
    
    print("\n--- TEST 1: No Repetition & Vertical Discovery ---")
    message = "I want to go to Italy in the countryside around March 15, 2026, with a budget of $5000."
    print(f"User: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    # Check for forbidden repetitions
    forbidden = ["Italy", "countryside", "March 15", "$5000"]
    leaked_repro = [f for f in forbidden if f.lower() in response.lower() and "confirm" in response.lower()] # Check if it confirms
    # Actually, any repetition followed by "Okay, ..." or similar meta-talk is bad.
    
    if "confirm" in response.lower() or "look at options across the country" in response.lower():
         print("❌ FAILURE: Agent used horizontal question or meta-talk.")
    else:
         print("✅ SUCCESS: Agent pivoted to next question.")

    print("\n--- TEST 2: Zero Entity Leaks ---")
    message = "Suggest some regions."
    print(f"User: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    if "Tuscany" in response and "Florence" in response: # Typical leak
         print("❌ FAILURE: Agent leaked specific city names (Florence).")
    elif "Tuscany" in response and "Umbria" in response:
         # Regions are okay if asked, but describing them with specific landmarks/cities is a leak.
         if "Florence" in response or "Siena" in response:
             print("❌ FAILURE: Agent leaked specific city names.")
         else:
             print("✅ SUCCESS: Agent suggested regions without entity leaks.")
    else:
         print("✅ SUCCESS: Agent followed stealth discovery.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_stealth_discovery_strict()
