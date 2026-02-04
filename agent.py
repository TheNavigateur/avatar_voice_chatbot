import os
import logging
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from tools.rfam_db import execute_sql_query
from tools.search_tool import perform_google_search
from booking_service import BookingService
from models import PackageItem, PackageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from profile_service import ProfileService
from memory_agent import MemoryAgent

# --- Tool Wrappers for Agent ---
def create_new_package_tool(session_id: str, title: str, package_type: str = "mixed"):
    """
    Creates a new package for the user.
    Args:
        session_id: The current session ID.
        title: Title of the package (e.g., 'Holiday to Paris').
        package_type: Type of package (holiday, party, shopping, activity, mixed).
    """
    # Map string to Enum
    try:
        p_type = PackageType(package_type.lower())
    except ValueError:
        p_type = PackageType.MIXED
        
    pkg = BookingService.create_package(session_id, title, p_type)
    return f"Created new package: {pkg.title} (ID: {pkg.id})"

def add_item_to_package_tool(session_id: str, package_id: str, item_name: str, item_type: str, price: float, description: str = ""):
    """
    Adds an item to an existing package.
    Args:
        session_id: The current session ID.
        package_id: The ID of the package to add to.
        item_name: Name of the item (e.g., 'Flight to Paris').
        item_type: Type of item (flight, hotel, activity, product).
        price: Estimated price.
        description: Optional description.
    """
    item = PackageItem(name=item_name, item_type=item_type, price=price, description=description)
    pkg = BookingService.add_item_to_package(session_id, package_id, item)
    if pkg:
        return f"Added {item_name} to package {pkg.title}. Total items: {len(pkg.items)}. Total Price: {pkg.total_price}"
    return "Failed to find package."

def update_profile_memory_tool(user_id: str, fact: str):
    """
    Saves a persistent fact about the user to their profile.
    Args:
        user_id: The user's ID.
        fact: The fact to save (e.g., 'User is vegan', 'User likes easy hiking').
    """
    new_content = ProfileService.append_to_profile(user_id, fact)
    return f"Saved to profile: {fact}"


class VoiceAgent:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set. Agent will fail to run.")

        # Initialize Session Service (no app_name argument)
        # We keep this global to persist sessions across requests
        self.session_service = InMemorySessionService()
        self.memory_agent = MemoryAgent()

    def process_message(self, user_id: str, session_id: str, message: str) -> str:
        """
        Process a text message and return the text response.
        """
        logger.info(f"Processing message: {message}")
        
        # --- ACTIVE MEMORY: Structured Rewrite ---
        try:
            # 1. Get current profile
            current_profile = ProfileService.get_profile(user_id)
            
            # 2. Get context (Last Bot Message) from Session Service
            last_bot_message = "None (Start of conversation)"
            
            # We need to fetch the session blindly first to get history
            # This is a bit chicken-and-egg as runner creates session if missing, 
            # but we can try to peek.
            try:
                 session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
                 if session and session.events:
                     # Find last model message
                     for i in range(len(session.events) - 1, -1, -1):
                         event = session.events[i]
                         # Check for model text content
                         if getattr(event, 'author', '') == 'model' or getattr(event, 'role', '') == 'model':
                             # Extract text (simplified extraction logic similar to bottom of file)
                             text = ""
                             if hasattr(event, 'text') and event.text: text = event.text
                             elif hasattr(event, 'content'):
                                 if hasattr(event.content, 'parts'):
                                     text = " ".join([p.text for p in event.content.parts if hasattr(p, 'text') and p.text])
                                 elif hasattr(event.content, 'text'):
                                     text = event.content.text
                             
                             if text:
                                 last_bot_message = text
                                 break
            except Exception as e:
                logger.warning(f"Could not fetch session history for memory context: {e}")

            # 3. Rewrite Profile
            logger.info(f"Updating profile with context: User='{message}', Bot='{last_bot_message[:50]}...'")
            new_profile = self.memory_agent.update_structured_profile(current_profile, last_bot_message, message)
            
            # 4. Save
            ProfileService.update_profile(user_id, new_profile)
            
        except Exception as e:
            logger.error(f"Failed to execute Active Memory update: {e}")

        # Re-fetch updated profile for the Main Agent context
        user_profile = ProfileService.get_profile(user_id)
        
        # Initialize Model, Agent, and Runner for EACH request
        model = Gemini(model="gemini-2.0-flash")
        
        # Bind tools with session_id
        def create_package_bound(title: str, package_type: str = "mixed"):
            """Creates a new package. Use this when you have enough info to start a collection of items."""
            return create_new_package_tool(session_id, title, package_type)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, description: str = ""):
            """Adds an item to a package. Use this to populate the package."""
            return add_item_to_package_tool(session_id, package_id, item_name, item_type, price, description)

        def save_user_info_bound(fact: str):
            """Saves a permanent fact or preference about the user to their 'About Me' profile."""
            return update_profile_memory_tool(user_id, fact)

        agent = Agent(
            name="ray_and_rae",
            model=model,
            tools=[perform_google_search, create_package_bound, add_item_bound, save_user_info_bound],
            instruction=f"""You are "Ray and Rae", an intelligent AI assistant who helps users plan holidays, parties, shopping trips, and local activities.
            
            **User Profile (Read-Only Context):**
            {user_profile}
            
            **Your Goal:**
            Gather requirements from the user until you have enough information to create a concrete "Package".
            
            **How to work:**
            1.  **Check Profile:** Always use the user's profile context (above) to personalize suggestions.
            2.  **Discuss & Clarify:** Talk to the user.
            3.  **Update Profile (`save_user_info_bound`):** If the user tells you a PERMANENT preference (e.g., "I am vegan", "I have 2 kids"), SAVE IT immediately.
            4.  **Create Package (`create_package_bound`):** Start a package when appropriate.
            5.  **Add Items (`add_item_bound`):** Populate the package.
            
            **Important Rules:**
            -   "A Package" is something that can be paid for directly.
            -   Use Google Search for real prices/options.
            -   **Memory:** If you learn something new and enduring about the user, use `save_user_info_bound`.
            
            **Expression Tagging:**
            -   Begin every response with `[Expression: EmotionName]`.
            -   Emotions: `Neutral`, `Happy`, `Sad`, `Surprised`, `Thinking`, `Angry`, `Confused`.
            
            End with a helpful question or confirmation.
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
                                print(f"Returning from session events (parts): {response}")
                                return response
                        elif hasattr(event.content, 'text') and event.content.text:
                            print(f"Returning from session events (content.text): {event.content.text}")
                            return event.content.text
                        else:
                            # Try converting content to string
                            content_str = str(event.content)
                            if content_str and content_str != "":
                                print(f"Returning content as string: {content_str[:100]}...")
                                return content_str
            
            logger.warning("No response found in any location")
            return "I processed the request but have no response."

        except Exception as e:
            logger.error(f"Error running agent: {e}", exc_info=True)
            return f"Error: {str(e)}"

# Global instance
voice_agent = VoiceAgent()
