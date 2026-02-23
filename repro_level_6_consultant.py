import logging
import json
from agent import VoiceAgent
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_level_6_consultant():
    user_id = "web_user_v17_l6"
    session_id = "session_v17_l6"
    current_time = "2026-02-23 00:05:06"
    
    agent = VoiceAgent()
    
    def process(msg):
        print(f"\nUser: {msg}")
        full_response = ""
        for event_type, content in agent.process_message_stream(user_id, session_id, msg, current_time=current_time):
            if event_type == "text":
                full_response += content
        print(f"Agent: {full_response}")
        return full_response

    print("\n--- Level 6 Consultant Discovery Test ---")
    
    # Turn 1: Initial Discovery
    # EXPECTED: Resolve Logistics (Date/Duration) or Origin. NO "Where?".
    process("Holiday in 2027 please!")
    
    # Turn 2: Providing Dates
    # EXPECTED: Resolve Budget (Economy).
    process("I'm thinking of departing from London on March 25th for 10 days.")
    
    # Turn 3: Providing Budget
    # EXPECTED: Resolve Vision (Nature of experience).
    process("Around 5000 pounds.")
    
    # Turn 4: Providing Vision
    # EXPECTED: Synthesis and follow-up style-based question about internal candidates.
    process("I want a deeply private sanctuary feel, maybe some turquoise waters and local history.")

if __name__ == "__main__":
    test_level_6_consultant()
