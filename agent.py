import os
import logging
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from google.adk.tools import google_search

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAgent:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set. Agent will fail to run.")

        # Initialize Model
        # You can change the model name if needed
        self.model = Gemini(model="gemini-2.0-flash-exp")

        # Initialize Agent with Google Search Tool
        self.agent = Agent(
            name="google_search_voice_bot",
            model=self.model,
            tools=[google_search],
            instruction="""You are a helpful voice assistant. 
            Your primary capability is searching Google to answer user queries.
            Keep your responses concise and conversational, suitable for being spoken aloud.
            When you find information, summarize it clearly.
            Try to use no more than 10 words in your response.
            """
        )

        # Initialize Session Service (no app_name argument)
        self.session_service = InMemorySessionService()

        # Initialize Runner
        self.runner = Runner(
            agent=self.agent,
            app_name="voice_bot_app",
            session_service=self.session_service
        )

    def process_message(self, user_id: str, session_id: str, message: str) -> str:
        """
        Process a text message and return the text response.
        """
        logger.info(f"Processing message: {message}")
        
        accumulated_text = ""
        
        try:
            # Ensure a session exists; create if absent
            try:
                session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
            except Exception:
                session = None
            if not session:
                try:
                    self.session_service.create_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
                    logger.info(f"Created new session: {session_id}")
                except Exception as e:
                    logger.error(f"Failed to create session: {e}")

            # Convert string message to Content object
            from google.genai.types import Content, Part
            msg = Content(role="user", parts=[Part(text=message)])
            
            # Iterate through events to execute the agent
            for event in self.runner.run(user_id=user_id, session_id=session_id, new_message=msg):
                # Try to capture text from ModelResponse events
                if hasattr(event, 'text') and event.text:
                    logger.info(f"Captured text from event.text: {event.text}")
                    accumulated_text += event.text
                
                # Check for content attribute
                if hasattr(event, 'content'):
                    if hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                logger.info(f"Captured text from event.content.parts: {part.text}")
                                accumulated_text += part.text
                
                # Also check if it's a tool call or error
                if hasattr(event, 'tool_calls') and event.tool_calls:
                    logger.info(f"Tool calls: {event.tool_calls}")
                if hasattr(event, 'error'):
                    logger.error(f"Event error: {event.error}")

            # If we captured text during streaming/events, return it
            if accumulated_text.strip():
                return accumulated_text

            # Fallback: Check session events
            session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
            if session and session.events:
                # Look for the last model response in events
                for event in reversed(session.events):
                    if hasattr(event, 'role') and event.role == "model":
                        if hasattr(event, 'content') and hasattr(event.content, 'parts'):
                            return " ".join([p.text for p in event.content.parts if hasattr(p, 'text')])
                        elif hasattr(event, 'content'):
                            return str(event.content)
            
            return "I processed the request but have no response."

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return f"Error: {str(e)}"

# Global instance
voice_agent = VoiceAgent()
