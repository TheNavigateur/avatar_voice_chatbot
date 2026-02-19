import os
import uuid
import logging
from agent import voice_agent

# Configure logging to see the error
logging.basicConfig(level=logging.INFO)

def test_unknown_session():
    user_id = "test_user_new"
    session_id = str(uuid.uuid4())
    message = "Hi!"
    
    print(f"Testing with unknown session_id: {session_id}")
    
    try:
        # This sollte now work because VoiceAgent.process_message_stream ensures the session exists
        response = voice_agent.process_message(user_id, session_id, message)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Caught error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Ensure GOOGLE_API_KEY is set (or use what's in the env)
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Warning: GOOGLE_API_KEY not set")
    
    test_unknown_session()
