import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_iterative_discovery():
    user_id = "test_user_discovery_v13"
    session_id = "test_session_discovery_v13"
    current_time = "2026-02-22 13:02:15"
    
    # 1. Generic Start
    print("\n--- Turn 1: Italy trip please ---")
    message = "Italy trip please!"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 2. Experiential Choice: Countryside
    print("\n--- Turn 2: Choice (Countryside) ---")
    message = "Countryside"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 3. Experiential Choice: Relaxing
    print("\n--- Turn 3: Choice (Relaxing) ---")
    message = "Relaxing"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_iterative_discovery()
