import os
import logging
from memory_agent import MemoryAgent

# Mock logging
logging.basicConfig(level=logging.INFO)

def test_memory():
    print("Initializing MemoryAgent...")
    try:
        agent = MemoryAgent()
    except Exception as e:
        print(f"Failed to init MemoryAgent: {e}")
        return

    current = "# About Me\n- I am a new user."
    bot_msg = "Where would you like to go?"
    user_msg = "I want to go to Paris."

    print("Running update...")
    try:
        new_profile = agent.update_structured_profile(current, bot_msg, user_msg)
        print("\n--- RESULT ---")
        print(new_profile)
        print("--------------")
    except Exception as e:
        print(f"Failed to update: {e}")

if __name__ == "__main__":
    # Ensure env var is set if possible, or assume source secrets.sh handled it
    if not os.environ.get("GOOGLE_API_KEY"):
         print("WARNING: GOOGLE_API_KEY not found in env")
    test_memory()
