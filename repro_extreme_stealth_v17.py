import os
import logging
from agent import voice_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_extreme_stealth_v17():
    user_id = "web_user_v17_l4"
    session_id = "session_v17_l4"
    current_time = "2026-02-22 22:05:06"
    
    def process(msg):
        print(f"User: {msg}")
        for event_type, content in voice_agent.process_message_stream(user_id, session_id, msg, current_time=current_time):
            if event_type == "text":
                print(content, end="", flush=True)
            elif event_type == "tool":
                print(f"\n[TOOL CALL: {content}]")
            elif event_type == "error":
                print(f"\n[ERROR: {content}]")
        print()

    # 1. Start with broad year
    print("\n--- Turn 1: Holiday in 2027 ---")
    process("I want a holiday in 2027 please!")

    # 2. Vibe Choice
    print("\n--- Turn 2: Relaxing Beach Getaway ---")
    process("Relaxing Beach Getaway")

    # 3. Setting Date & Origin
    print("\n--- Turn 3: London, March 25th ---")
    process("I'm departing from London on March 25th")

    # 4. Choosing Style (Should be anonymous)
    print("\n--- Turn 4: Turquoise Waters ---")
    process("Turquoise waters")

    # 5. Day 1 Activity Choice (Should be experiential style, not specific spot)
    print("\n--- Turn 5: Style for Day 1? ---")
    process("Relaxing and mixed")

    # 6. Activity Selection (Check for Anonymity & Styles)
    print("\n--- Turn 6: Specific Experience for Day 1? ---")
    process("Lively atmosphere")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_extreme_stealth_v17()

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_extreme_stealth_v17()
