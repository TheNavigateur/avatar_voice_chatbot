import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_stealth_discovery_multiturn():
    user_id = "test_user_stealth_multi"
    session_id = "test_session_stealth_multi"
    
    # Simulate a user who has already expressed general interest and is now being more specific
    # In the real failure, the user said "Lively après-ski for a beginner skier"
    message = "I want a lively après-ski scene but I'm a beginner skier"
    print(f"\nUser: {message}")
    
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    bad_keywords = ["Pas de la Casa", "St Anton", "Andorra", "Austria", "St. Anton"]
    found_bad = [kw for kw in bad_keywords if kw.lower() in response.lower()]
    
    if found_bad:
        print(f"\n❌ FAILURE: Agent leaked specific locations/resorts: {found_bad}")
    elif "[RESPONSE_OPTIONS" in response:
        print("\n✅ SUCCESS: Agent used [RESPONSE_OPTIONS] to narrow by experience without naming resorts.")
    else:
        print("\n⚠️ UNCERTAIN: Agent didn't leak names but might not have used [RESPONSE_OPTIONS]. Check output.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_stealth_discovery_multiturn()
