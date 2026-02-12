import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_destination_inference():
    user_id = "test_user_weather_2"
    session_id = "test_session_weather_2"
    
    # Step 1: Initial greeting
    print(f"\nUser: Hi")
    response1 = voice_agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {response1}")
    
    # Step 2: User provides weather preference
    message = "Yeah I want 26 degrees in the day though"
    print(f"\nUser: {message}")
    
    response2 = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent: {response2}")
    
    # Check if the agent asks "Where" or similar
    bad_phrases = ["where are you thinking", "where do you want to go", "what destination"]
    found_bad = any(phrase in response2.lower() for phrase in bad_phrases)
    
    if found_bad:
        print("\n❌ REPRODUCED: Agent asked for the destination.")
    else:
        print("\n✅ SUCCESS: Agent did not ask for the destination.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_destination_inference()
