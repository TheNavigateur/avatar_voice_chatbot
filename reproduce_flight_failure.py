import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_flight_search_failure():
    user_id = "test_user_flight"
    session_id = "test_session_flight"
    
    # Simulate user request that failed in the report, including context
    message = "I want to go for 15 days starting March 15, 2026. Search the flight from Doha Qatar to Rome and from there you can find me any rental car options for driving to Tuscany"
    print(f"\nUser: {message}")
    
    # We need to set a current time to avoid relative time issues if any
    current_time = "2026-02-21 22:00:00"
    
    response = voice_agent.process_message(user_id, session_id, message, current_time=current_time)
    print(f"Agent: {response}")
    
    if "couldn't find any flights" in response.lower() or "no flights found" in response.lower():
        print(f"\n❌ REPRODUCED: Agent failed to find flights from Doha to Rome.")
    else:
        print(f"\n✅ SUCCESS: Agent found flights (or at least didn't report failure).")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    elif not os.environ.get("DUFFEL_ACCESS_TOKEN"):
        print("Please set DUFFEL_ACCESS_TOKEN")
    else:
        test_flight_search_failure()
