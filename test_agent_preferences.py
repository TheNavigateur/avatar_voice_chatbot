import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_preference_flow():
    user_id = "test_user_123"
    session_id = "test_session_456"
    
    # Simulate user saying "yeah let's do a water park"
    # Note: We assume Phase 1/2 are somehow skipped or handled for this isolated test
    # In a real scenario, this would be part of a larger conversation.
    # We will just see how the agent responds to the specific request for a water park.
    
    message = "yeah let's do a water park"
    print(f"\nUser: {message}")
    
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response}")
    
    # Check if the agent asks a preference question instead of listing Siam Park vs Aqualand
    if "Siam Park" in response and "Aqualand" in response and ("better" in response or "choice" in response):
        print("\n❌ FAILURE: Agent presented a menu.")
    else:
        print("\n✅ SUCCESS: Agent likely asked for a preference or recommended one.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_preference_flow()
