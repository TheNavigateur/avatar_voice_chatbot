import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_initial_turn():
    user_id = "repro_user_v1"
    session_id = "repro_session_v1"
    current_time = "2026-02-22 12:58:48"
    
    # 1. Start trip
    print("\n--- Turn 1: Start ---")
    message = "Italy trip please!"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_initial_turn()
