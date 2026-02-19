
import os
import sys
from agent import voice_agent

def test_hi_greeting():
    user_id = "test_user"
    session_id = "test_session"
    message = "Hi!"
    
    print(f"--- Sending message: '{message}' ---")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"--- Response ---")
    print(response)
    print("----------------")

if __name__ == "__main__":
    test_hi_greeting()
