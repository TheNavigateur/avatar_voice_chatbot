import logging
import json
import os
from agent import VoiceAgent
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_large_context_breach():
    # Use the same user ID as the reported error
    user_id = "web_user"
    session_id = "debug_session_v6"
    current_time = "2026-02-23 00:10:06"
    
    agent = VoiceAgent()
    
    def process(msg):
        print(f"\nUser: {msg}")
        full_response = ""
        for event_type, content in agent.process_message_stream(user_id, session_id, msg, current_time=current_time):
            if event_type == "text":
                full_response += content
        print(f"Agent: {full_response}")
        return full_response

    print("\n--- Level 6 Large Context Test ---")
    
    # Turn 1: Initial Discovery
    # EXPECTED: Resolve Logistics (Date/Duration) or Origin. NO "Where?".
    process("Holiday in 2027 please!")

if __name__ == "__main__":
    test_large_context_breach()
