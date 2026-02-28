import os
import sys
# Add current directory to path
sys.path.append(os.getcwd())

from agent import voice_agent

def test_transparency_stream():
    user_id = "test_user"
    session_id = "test_session"
    message = "search for flights from London to Paris today"
    
    print(f"Testing stream for message: '{message}'")
    events_received = []
    
    # We'll just run a few events to see if 'thinking' is there
    # Note: This will make actual API calls unless mocked.
    # For verification, we just want to see if the generator yields what we added.
    
    try:
        generator = voice_agent.process_message_stream(user_id, session_id, message)
        
        count = 0
        thinking_found = False
        text_found = False
        
        for event_type, content in generator:
            print(f"[{event_type.upper()}] {str(content)[:100]}...")
            events_received.append(event_type)
            if event_type == "thinking":
                thinking_found = True
            if event_type == "text":
                text_found = True
            
            count += 1
            if count > 20: # Limit for test
                break
                
        if thinking_found:
            print("\nSUCCESS: 'thinking' events found in stream.")
        else:
            print("\nFAILURE: No 'thinking' events found in stream.")
            
    except Exception as e:
        print(f"\nERROR during stream test: {e}")

if __name__ == "__main__":
    if "GOOGLE_API_KEY" not in os.environ:
        print("Warning: GOOGLE_API_KEY not set. Test might fail on first model call.")
    test_transparency_stream()
