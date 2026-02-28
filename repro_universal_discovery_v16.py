import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_universal_discovery_v16():
    user_id = "unique_repro_v16"
    session_id = "unique_session_v16"
    current_time = "2026-02-22 13:32:30"
    
    # 1. No Location Start
    print("\n--- Turn 1: I need a holiday ---")
    message = "I need a holiday!"
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 2. Hybrid Choice
    print("\n--- Turn 2: I want a bit of both actually ---")
    message = "I want a bit of both actually, vibrant but with some peace too"
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_universal_discovery_v16()
