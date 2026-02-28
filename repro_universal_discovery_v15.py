import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_universal_discovery_v15():
    user_id = "test_user_v15"
    session_id = "test_session_v15"
    current_time = "2026-02-22 13:32:30"
    
    # 1. No Location Start (Global Contrast)
    print("\n--- Turn 1: I need a holiday ---")
    message = "I need a holiday!"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 2. Nuanced/Hybrid Choice
    print("\n--- Turn 2: I want a bit of both actually ---")
    message = "I want a bit of both actually, vibrant but with some peace too"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 3. Requesting missing info (Origin)
    print("\n--- Turn 3: Departing from London, March ---")
    message = "I'm departing from London in March"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 4. Final Choice: Rome
    print("\n--- Turn 4: Choice (Rome & Countryside) ---")
    message = "Rome & Countryside"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_universal_discovery_v15()
