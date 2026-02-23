import logging
import json
from agent import VoiceAgent
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_level_5_discovery():
    user_id = "web_user_v17_l5"
    session_id = "session_v17_l5"
    current_time = "2026-02-22 22:05:06"
    
    agent = VoiceAgent()
    
    def process(msg):
        print(f"\nUser: {msg}")
        full_response = ""
        for event_type, content in agent.process_message_stream(user_id, session_id, msg, current_time=current_time):
            if event_type == "text":
                full_response += content
        print(f"Agent: {full_response}")
        return full_response

    print("\n--- Level 5 Discovery Test ---")
    
    # Turn 1: Initial Discovery
    # EXPECTED: Open-ended question about the nature of the experience, NO binary choice.
    process("I want a holiday in 2027 please!")
    
    # Turn 2: User provides vision
    # EXPECTED: Synthesis and follow-up open-ended question.
    process("I'm looking for a mix of deep relaxation on a beach and some high-end local culture.")
    
    # Turn 3: Date and Origin
    process("I'm departing from London on March 25th")
    
    # Turn 4: Final vision clarification
    process("April 10th. I want a deeply private sanctuary feel for my stay.")

if __name__ == "__main__":
    test_level_5_discovery()
