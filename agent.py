import os
import logging
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from tools.rfam_db import execute_sql_query
from tools.search_tool import perform_google_search

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceAgent:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set. Agent will fail to run.")

        # Initialize Session Service (no app_name argument)
        # We keep this global to persist sessions across requests
        self.session_service = InMemorySessionService()

    def process_message(self, user_id: str, session_id: str, message: str) -> str:
        """
        Process a text message and return the text response.
        """
        logger.info(f"Processing message: {message}")
        
        # Initialize Model, Agent, and Runner for EACH request
        # This ensures we get a fresh HTTP client and event loop context
        # preventing "Event loop is closed" errors
        model = Gemini(model="gemini-2.0-flash-exp")
        
        agent = Agent(
            name="google_search_voice_bot",
            model=model,
            tools=[perform_google_search, execute_sql_query],
            instruction="""You are a helpful voice assistant with access to the Rfam public database and Google Search.
            
            Your capabilities:
            1. **Google Search**: Use `perform_google_search` for general knowledge questions or current events.
            2. **Rfam Database**: Use `execute_sql_query` to answer questions about RNA families.
            
            **Rfam Database Schema:**
            - **family** table:
                - `rfam_acc` (e.g., RF00001): Accession number
                - `rfam_id` (e.g., 5S_rRNA): Family name/ID
                - `description`: Description of the family
                - `type`: Type of RNA (e.g., rRNA, tRNA, cis-reg)
                - `number_of_species`: Number of species in the family
                - `author`: Author of the family
            - **clan** table:
                - `clan_acc`: Clan accession
                - `id`: Clan ID
                - `description`: Clan description
            - **taxonomy** table:
                - `ncbi_id`: NCBI Taxonomy ID
                - `species`: Species name
                - `tax_string`: Taxonomy string
            - **rfamseq** table:
                - `rfamseq_acc`: Sequence accession
                - `description`: Sequence description
                - `mol_type`: Molecule type (e.g., rRNA, tRNA)
            
            **Instructions for Database Queries:**
            - When a user asks a question about RNA families, convert it into a valid MySQL query.
            - Use `LIKE` for text searches (e.g., `WHERE description LIKE '%keyword%'`).
            - Always limit results if not counting (e.g., `LIMIT 5`).
            - Execute the query using `execute_sql_query`.
            - Summarize the results in natural language.
            
            Keep your spoken responses concise (under 20 words if possible) unless listing results.
            
            **Expression Tagging:**
            - You MUST begin every response with an emotion tag in the format `[Expression: EmotionName]`.
            - Allowed Emotions: `Neutral`, `Happy`, `Sad`, `Surprised`, `Thinking`, `Angry`, `Confused`.
            - Choose the emotion that best fits the content of your response.
            - Example: `[Expression: Happy] I found 5 results for that query!`

            ALWAYS end your final response or turn with a question like "Can I help you with anything else?" or "Is there anything else?" to invite further conversation.
            
            HOWEVER, if the user explicitly says "no", "nothing else", "stop", "bye", or otherwise indicates they are done:
            1. Respond with a polite message like "Okay, goodbye! If you need any more help, just press the 'Start Conversation' button."
            2. APPEND the token `[END_CONVERSATION]` to the very end of your response.
            """
        )
        
        runner = Runner(
            agent=agent,
            app_name="voice_bot_app",
            session_service=self.session_service
        )
        
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
            for event in runner.run(user_id=user_id, session_id=session_id, new_message=msg):
                event_author = getattr(event, 'author', None)
                logger.info(f"Event type: {type(event).__name__}, author: {event_author}")
                
                # Try to capture text from ModelResponse events
                if hasattr(event, 'text') and event.text:
                    logger.info(f"Captured text from event.text: {event.text}")
                    accumulated_text += event.text
                
                # Check for content attribute
                if hasattr(event, 'content'):
                    # Only process if this is from the model (not user)
                    if event_author and event_author != 'user':
                        if hasattr(event.content, 'parts'):
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    logger.info(f"Captured text from event.content.parts (author={event_author}): {part.text}")
                                    accumulated_text += part.text
                        # Sometimes content itself has text
                        elif hasattr(event.content, 'text') and event.content.text:
                            logger.info(f"Captured text from event.content.text (author={event_author}): {event.content.text}")
                            accumulated_text += event.content.text
                
                # Check for message attribute (some events use this)
                if hasattr(event, 'message'):
                    if hasattr(event.message, 'content'):
                        if hasattr(event.message.content, 'parts'):
                            for part in event.message.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    logger.info(f"Captured text from event.message.content.parts: {part.text}")
                                    accumulated_text += part.text
                
                # Also check if it's a tool call or error
                if hasattr(event, 'tool_calls') and event.tool_calls:
                    logger.info(f"Tool calls: {event.tool_calls}")
                if hasattr(event, 'error'):
                    logger.error(f"Event error: {event.error}")

            # If we captured text during streaming/events, return it
            if accumulated_text.strip():
                logger.info(f"Returning accumulated text: {accumulated_text}")
                return accumulated_text

            # Fallback: Check session events
            logger.info("No text accumulated, checking session events...")
            session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
            if session and session.events:
                logger.info(f"Session has {len(session.events)} events")
                
                # Find the index of the last user message
                last_user_msg_index = -1
                for i, event in enumerate(session.events):
                    event_role = getattr(event, 'role', 'N/A')
                    event_author = getattr(event, 'author', 'N/A')
                    if event_role == 'user' or event_author == 'user':
                        last_user_msg_index = i
                
                logger.info(f"Last user message index: {last_user_msg_index}")

                # Look for model response ONLY after the last user message
                # We iterate from the end, but stop if we reach the user message
                for i in range(len(session.events) - 1, last_user_msg_index, -1):
                    event = session.events[i]
                    event_role = getattr(event, 'role', 'N/A')
                    event_author = getattr(event, 'author', 'N/A')
                    logger.info(f"Checking event {i}: type={type(event).__name__}, role={event_role}, author={event_author}")
                    
                    # Skip user messages (though we shouldn't see them if logic is correct)
                    if event_role == 'user' or event_author == 'user':
                        continue
                    
                    # Try to extract content from model events
                    if hasattr(event, 'content'):
                        logger.info(f"Event has content attribute: {type(event.content)}")
                        if hasattr(event.content, 'parts'):
                            parts_text = []
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    parts_text.append(part.text)
                                    logger.info(f"Found text in part: {part.text[:50]}...")
                            if parts_text:
                                response = " ".join(parts_text)
                                logger.info(f"Returning from session events (parts): {response}")
                                return response
                        elif hasattr(event.content, 'text') and event.content.text:
                            logger.info(f"Returning from session events (content.text): {event.content.text}")
                            return event.content.text
                        else:
                            # Try converting content to string
                            content_str = str(event.content)
                            if content_str and content_str != "":
                                logger.info(f"Returning content as string: {content_str[:100]}...")
                                return content_str
            
            logger.warning("No response found in any location")
            return "I processed the request but have no response."

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return f"Error: {str(e)}"

# Global instance
voice_agent = VoiceAgent()
