import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_stealth_discovery_history_neutralization():
    user_id = "test_user_history_pivot"
    session_id = "test_session_history_pivot"
    
    # Simulate a user asking to choose between previously leaked hotel names
    message = "Can you help me choose between Pension St Anton and Apart Gabriele?"
    print(f"\nUser: {message}")
    
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    bad_keywords = ["Pension St Anton", "Der Steinbock", "Apart Gabriele", "Gästehaus Schön", "Schon", "Pension", "Gabriele"]
    found_bad = [kw for kw in bad_keywords if kw.lower() in response.lower()]
    
    if found_bad:
        print(f"\n❌ FAILURE: Agent repeated specific hotel names from history: {found_bad}")
    elif "[RESPONSE_OPTIONS" in response:
        print("\n✅ SUCCESS: Agent neutralized history and switched back to experiential options.")
    else:
        print("\n⚠️ UNCERTAIN: Agent didn't leak names but might not have pivoted to experiences.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_stealth_discovery_history_neutralization()
