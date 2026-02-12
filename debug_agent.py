from agent import VoiceAgent
import logging
import sys

# Configure logging to console
logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

def test_agent():
    agent = VoiceAgent()
    user_id = "test_user_debug"
    session_id = "test_session_debug"
    
    # 1. First message to warm up
    print("\n--- Sending Message 1 ---")
    tool_calls_made = []
    # Assuming process_message returns an iterable of events, and the final response is the last event or accumulated
    response_events = agent.process_message(user_id, session_id, "Hello")
    final_response_1 = ""
    for event in response_events:
        if hasattr(event, 'tool_calls') and event.tool_calls:
            logger.info(f"Tool calls: {event.tool_calls}")
            # Extract tool names and arguments
            for tc in event.tool_calls:
                if hasattr(tc, 'name'):
                    args = getattr(tc, 'args', {})
                    print(f"\n[DEBUG] Tool Call: {tc.name}")
                    print(f"[DEBUG] Arguments: {args}\n")
                    tool_calls_made.append(tc.name)
        # Assuming the event itself might contain the response or parts of it
        # This part might need adjustment based on the actual structure of 'event'
        if hasattr(event, 'response_text'): # Example: if event has a response_text attribute
            final_response_1 += event.response_text
        elif isinstance(event, str): # Example: if events are just strings
            final_response_1 += event
        # If process_message returns a single response object directly, the loop is not needed.
        # For this change, we'll assume it's an iterable of events.
    
    print(f"Response 1: {final_response_1}")
    
    # 2. problematic message
    print("\n--- Sending Message 2 (The problematic one) ---")
    try:
        # This call remains as is, assuming the debug logging is only for the first message as per instruction placement
        response = agent.process_message(user_id, session_id, "can you add an umbrella and sun cream please")
        print(f"Response 2: {response}")
    except Exception as e:
        print(f"CRASH: {e}")

if __name__ == "__main__":
    test_agent()
