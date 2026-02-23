import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_stealth_discovery_regions():
    user_id = "test_user_stealth_regions"
    session_id = "test_session_stealth_regions"
    
    print("\n--- TEST: Region-less Discovery ---")
    message = "A trip to italy please!"
    print(f"User: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    # Next step: Provide dates
    message = "Next month"
    print(f"User: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    forbidden_terms = ["Tuscany", "Amalfi", "Puglia", "Lake Como", "Sicily"]
    found_forbidden = [f for f in forbidden_terms if f.lower() in response.lower()]
    
    if found_forbidden:
         print(f"❌ FAILURE: Agent mentioned regions: {found_forbidden}")
    else:
         print("✅ SUCCESS: Agent did not mention regions.")

    if "[RESPONSE_OPTIONS:" in response:
        options_part = response.split("[RESPONSE_OPTIONS:")[1].split("]")[0]
        found_forbidden_options = [f for f in forbidden_terms if f.lower() in options_part.lower()]
        if found_forbidden_options:
            print(f"❌ FAILURE: Agent used regions in response options: {found_forbidden_options}")
        else:
            print("✅ SUCCESS: Response options are stealth.")
    else:
        print("⚠️ WARNING: No response options found.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_stealth_discovery_regions()
