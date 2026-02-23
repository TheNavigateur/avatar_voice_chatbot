import logging
import json
import os
from agent import VoiceAgent
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_day_jump_fixed():
    user_id = "web_user"
    session_id = "debug_sequential_v2"
    current_time = "2026-02-23 00:15:00"
    
    agent = VoiceAgent()
    
    def process(msg):
        print(f"\nUser: {msg}")
        full_response = ""
        for event_type, content in agent.process_message_stream(user_id, session_id, msg, current_time=current_time):
            if event_type == "text":
                full_response += content
        print(f"Agent: {full_response}")
        return full_response

    print("\n--- Day Jump Verification (Fixed) ---")
    
    # Turn 1: Logistics (Complete)
    process("Italy trip, March 15th 2027 for 10 days, departing from London")
    
    # Turn 2: Economy
    # Budget is part of hierarchy
    process("Budget around 5000 pounds")
    
    # Turn 5: Final Vision (Pace)
    # This should trigger Day 1.
    process("Balanced")

if __name__ == "__main__":
    test_day_jump_fixed()
