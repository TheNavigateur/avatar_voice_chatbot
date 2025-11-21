import os
import logging
import sys
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from google.adk.tools import google_search

# Setup logging to console
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

# Ensure keys are set (they should be in env from run.sh, but we'll check)
if "GOOGLE_API_KEY" not in os.environ:
    print("ERROR: GOOGLE_API_KEY not set")
    sys.exit(1)

from google.genai.types import Content, Part

def debug_run():
    print("Initializing Agent...")
    model = Gemini(model="gemini-1.5-flash")
    agent = Agent(name="debug_bot", model=model, tools=[google_search])
    session_service = InMemorySessionService()
    runner = Runner(agent=agent, app_name="debug_app", session_service=session_service)

    print("Running Agent...")
    try:
        # Create session
        session = session_service.create_session(app_name="debug_app", user_id="debug_user", session_id="debug_session")
        print(f"Session created: {session.session_id}")

        # Run with a simple query
        msg = Content(role="user", parts=[Part(text="Who is the CEO of Google?")])
        for event in runner.run(user_id="debug_user", session_id="debug_session", new_message=msg):
            print(f"\n--- Event Type: {type(event)} ---")
            print(f"Dir: {dir(event)}")
            
            # Try to print interesting attributes
            if hasattr(event, 'text'):
                print(f"Text: {event.text}")
            if hasattr(event, 'content'):
                print(f"Content: {event.content}")
            if hasattr(event, 'tool_calls'):
                print(f"Tool Calls: {event.tool_calls}")
            if hasattr(event, 'tool_outputs'):
                print(f"Tool Outputs: {event.tool_outputs}")
                
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_run()
