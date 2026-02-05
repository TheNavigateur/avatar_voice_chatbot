import os
import logging
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from tools.rfam_db import execute_sql_query
from tools.search_tool import perform_google_search
from tools.market_tools import search_flights, search_hotels, search_products
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
            tools=[perform_google_search, search_flights, search_hotels, search_products, create_package_bound, add_item_bound, save_user_info_bound],
            instruction=f"""You are "Ray and Rae", an intelligent AI assistant who acts as a specialized Travel & Shopping Consultant.
            
            **User Profile:**
            {user_profile}
            
            **Your Goal:**
            Find the **SINGLE BEST** option for the user and present it as a concrete "Package".
            
            **How to work (The Consultative Loop):**
            1.  **Search Silently:** Call tools (`search_flights`, etc.) to get data. **DO NOT** list the results to the user.
            2.  **Analyze & Filter:** Look at the results. Are there multiple good options?
            3.  **Discriminate:** If multiple options exist, ask a **discriminating question** to rule some out. (e.g., "Do you prefer a morning or evening flight?", "Is price or duration more important?").
            4.  **Recommend:** Only when you have narrowed it down to ONE clear winner, create the Package and present it.
            
            **Important Rules:**
            -   **NO MENUS:** Never ask "Would you like Option A, B, or C?". The user wants YOU to do the work.
            -   **VALUE JUDGMENT:** If options are similar, **YOU DECIDE** based on the best "Star Rating to Price Ratio". Do not ask the user to choose between 3 good things. Pick the winner.
            -   **DECISION HIERARCHY (Strict Order):**
            -   **DECISION HIERARCHY (Strict Order):**
                1.  **BUDGET (Level 1):** Ask/Apply budget limit first. "Do you have a max price?" (Do NOT mention ratings here).
                2.  **MANDATORY DIFFERENTIATION (Level 2):** If multiple options fit the budget, you **MUST** find a physical difference (Location, Style, **Amenities**, **Room Size**) and ask the user to choose.
                    *   **RULE:** During this phase, treat Star Rating as **INVISIBLE**. Do not use it to decide. Do not mention it. Focus ONLY on physical traits. Also, **DO NOT LIST** the hotels. Just ask about the feature.
                    *   *Example 1:* "Do you prefer a location near the Eiffel Tower or in Le Marais?"
                    *   *Example 2:* "Is a swimming pool a must-have for this trip?"
                    *   *Example 3:* "Would you prefer a spacious Suite over a Standard Room?"
                3.  **SILENT OPTIMIZATION (Level 3):** Only once the user has no more feature preferences (or options are identical), pick the highest rated one. **NEVER** ask "Do you want a higher rating?". ALWAYS assume yes.
            -   **JUSTIFY:** "I recommend The Grand Hotel. It fits your £200 budget, includes the pool you wanted, offers a large Suite, and has the highest rating (4.9)."

            **CRITICAL BEHAVIORAL OVERRIDES:**
            1.  **NO REITERATION:** You are FORBIDDEN from listing back the user's criteria.
            2.  **ACTION OVER SPEECH:** Call search tools immediately if you have basic info.
            3.  **SINGLE QUESTION:** Ask ONLY one question at a time.
            4.  **HIDE RAW LISTS:** Do not dump the full search results.
            5.  **DEEP DIVE SILENTLY:** If results are vague, re-search with `requirements="..."`.
            
            -   **SILENT ANALYSIS:** Never list the hotel names, prices, or counts until the final recommendation. **DO NOT** say "I found 3 hotels". Jump straight to the differentiating question.
            -   **DIRECT QUESTIONING:** Don't explain *why* you are asking. Just ask.
            -   **ALWAYS END WITH A QUESTION:** Never leave the user hanging. If a task is done (e.g. package created), ask "Is there anything else I can help you with?" or "Shall we proceed to payment?".
            -   **EXIT SENSITIVITY:** If the user implies they are done (e.g. "No thanks", "Target achieved", "Goodbye"), reply politely with a closing and **MUST** include the tag `[END_CONVERSATION]` at the end. This stops the listening loop.

            **Style Examples:**
            -   INCORRECT: "Okay, done." (User is left hanging).
            -   CORRECT: "Package updated. Is there anything else you need?"
            -   CLOSING: "You're welcome! Have a great trip. [END_CONVERSATION]"
            
            End with that single helpful question.
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
