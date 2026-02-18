import os
import logging
from datetime import datetime, timedelta
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from tools.rfam_db import execute_sql_query
from tools.search_tool import perform_google_search
from tools.market_tools import search_products, check_amazon_stock, search_amazon, search_hotels, search_amazon_with_reviews
from services.duffel_service import DuffelService
from services.amadeus_service import AmadeusService
from services.image_search_service import ImageSearchService
from booking_service import BookingService
from models import PackageItem, PackageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from profile_service import ProfileService
from memory_agent import MemoryAgent

# --- Tool Wrappers for Agent ---
def create_new_package_tool(session_id: str, user_id: str, title: str, package_type: str = "mixed"):
    """
    Creates a new package for the user.
    Args:
        session_id: The current session ID.
        user_id: The current user ID.
        title: Title of the package (e.g., 'Holiday to Paris').
        package_type: Type of package (holiday, party, shopping, activity, mixed).
    """
    logger.info(f"[TOOL] Creating new package: '{title}' (Type: {package_type}) for User: {user_id}")
    # Map string to Enum
    try:
        p_type = PackageType(package_type.lower())
    except ValueError:
        p_type = PackageType.MIXED
        
    pkg = BookingService.create_package(session_id, title, p_type, user_id=user_id)
    logger.info(f"[TOOL] Package created successfully: {pkg.id}")
    return f"Created new package: {pkg.title} (ID: {pkg.id})"

def add_item_to_package_tool(session_id: str, package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None):
    """
    Adds an item to an existing package.
    Args:
        session_id: The current session ID.
        package_id: The ID of the package to add to.
        item_name: Name of the item (e.g., 'Flight to Paris').
        item_type: Type of item (flight, hotel, activity, product).
        price: Estimated price.
        description: Optional description.
        image_url: Optional primary URL of the product/activity/hotel image.
        product_url: Optional direct URL to the product page.
        day: Optional day number for itinerary (e.g., 1, 2, 3).
        date: Optional date string for itinerary (e.g., 'March 10, 2024').
        rating: Optional rating (e.g., 4.5 out of 5).
        review_link: Optional link to reviews.
        reviews: Optional list of objects with "text" and "rating" (e.g. [{"text": "Great!", "rating": 5}, ...]).
        images: Optional list of image URLs for carousel.
    """
    item = PackageItem(name=item_name, item_type=item_type, price=price, description=description)
    
    # --- IMAGE AUTO-FIX & FILTERING ---
    # 1. Helper to detect "bad" URLs
    def is_bad_url(url):
        if not url: return True
        return url == 'unknown' or ('amazon.' in str(url) and ('/dp/' in str(url) or '/gp/' in str(url)))

    # 2. Filter the incoming images list if provided
    if images:
        images = [img for img in images if not is_bad_url(img)]
    else:
        images = []

    # 3. Handle primary image_url
    if is_bad_url(image_url):
        image_url = None
    elif image_url not in images:
        images.insert(0, image_url)

    # 4. Search if we still need images
    if not images or len(images) < 3:
        try:
            image_service = ImageSearchService()
            pkg = BookingService.get_package(session_id, package_id)
            location = None
            if pkg and pkg.title:
                location = pkg.title.replace('Holiday', '').replace('Trip', '').replace('Getaway', '').strip()
            
            found_images = []
            if item_type == 'activity':
                found_images = image_service.get_activity_image(item_name, location, num=5)
            elif item_type == 'hotel':
                found_images = image_service.get_hotel_image(item_name, num=5)
            elif item_type == 'flight':
                found_images = image_service.get_flight_image(item_name, num=5)
            elif item_type == 'product':
                found_images = image_service.get_product_image(item_name, num=5)
            
            for img in found_images:
                if img not in images and not is_bad_url(img):
                    images.append(img)
                if len(images) >= 5:
                    break
        except Exception as e:
            logger.warning(f"Failed to auto-search images for {item_name}: {e}")

    # 5. Final fallback for primary image_url
    if not image_url and images:
        image_url = images[0]
    
    # 6. Final product-specific search if still no image
    if not image_url and item_type == 'product':
        logger.info(f"[TOOL] No image for product '{item_name}', searching...")
        try:
             found = ImageSearchService().get_product_image(item_name, num=1)
             if found:
                 image_url = found[0]
                 if image_url not in images:
                     images.insert(0, image_url)
        except Exception as e:
            logger.warning(f"Product image search failed: {e}")

    # Store extended details in metadata
    if images:
        item.metadata['images'] = images
        # Set primary image_url if not already set
        if not image_url:
            image_url = images[0]
            
    if image_url:
        item.metadata['image_url'] = image_url
    if product_url:
        item.metadata['product_url'] = product_url
    if day is not None:
        item.metadata['day'] = day
    if date:
        item.metadata['date'] = date
    if rating is not None:
        item.metadata['rating'] = rating
    if review_link:
        item.metadata['review_link'] = review_link
    if reviews:
        # Store up to top 10 reviews
        item.metadata['reviews'] = list(reviews)[:10]
        
    logger.info(f"[TOOL] Adding item '{item_name}' (Type: {item_type}) to package {package_id}")
    pkg = BookingService.add_item_to_package(session_id, package_id, item)
    if pkg:
        logger.info(f"[TOOL] Item added successfully. Total items: {len(pkg.items)}")
        return f"Added {item_name} to package {pkg.title}. Total items: {len(pkg.items)}. Total Price: {pkg.total_price}"
    logger.warning(f"[TOOL] Failed to find package {package_id}")
    return "Failed to find package."

def remove_item_from_package_tool(session_id: str, package_id: str, item_id: str):
    """
    Removes an item from an existing package.
    Args:
        session_id: The current session ID.
        package_id: The ID of the package to remove from.
        item_id: The ID of the item to remove.
    """
    logger.info(f"[TOOL] Removing item '{item_id}' from package {package_id}")
    pkg = BookingService.remove_item_from_package(session_id, package_id, item_id)
    if pkg:
        logger.info(f"[TOOL] Item removed successfully. Total items: {len(pkg.items)}")
        return f"Removed item from package {pkg.title}. Total items: {len(pkg.items)}. Total Price: {pkg.total_price}"
    logger.warning(f"[TOOL] Failed to find package {package_id} or item {item_id}")
    return "Failed to find package or item."

def update_profile_memory_tool(user_id: str, fact: str):
    """
    Saves a persistent fact about the user to their profile.
    Args:
        user_id: The user's ID.
        fact: The fact to save (e.g., 'User is vegan', 'User likes easy hiking').
    """
    new_content = ProfileService.append_to_profile(user_id, fact)
    return f"Saved to profile: {fact}"

def list_user_packages_tool(user_id: str):
    """
    Returns a natural language summary of all the user's saved lifestyle and travel packages.
    """
    logger.info(f"[TOOL] Listing packages for User: {user_id}")
    return BookingService.get_user_packages_summary(user_id)

def search_packages_tool(user_id: str, query: str = None, date_filter: str = None, package_type: str = None):
    """
    Searches for specific packages by keyword, date, or type.
    Args:
        user_id: The current user ID.
        query: Search term (e.g., 'Paris', 'Beach').
        date_filter: Year or month (e.g., '2024', 'March').
        package_type: Type of package (holiday, party, shopping, activity, mixed).
    """
    logger.info(f"[TOOL] Searching packages for User: {user_id} (Query: {query}, Date: {date_filter}, Type: {package_type})")
    results = BookingService.search_packages(user_id, query=query, start_date=date_filter, package_type=package_type)
    
    if not results:
        return f"No packages found matching your search criteria: {query or ''} {date_filter or ''}."
        
    summary = f"I found {len(results)} matching packages:\n"
    for p in results:
        summary += f"- {p.title} (Status: {p.status.value})\n"
    summary += "\nWhich one would you like to open? You can use the buttons provided below if you like."
    return summary

def get_package_details_tool(user_id: str, package_name_or_id: str):
    """
    Returns full details of a package (its items) by name or ID.
    Args:
        user_id: The current user ID.
        package_name_or_id: The name/title of the package (e.g., 'Maldives Trip') or its unique ID.
    """
    logger.info(f"[TOOL] Getting package details for: {package_name_or_id}")
    
    # Try by title first (most common for natural language)
    pkg = BookingService.get_package_by_title(user_id, package_name_or_id)
    
    # If not found, try by ID as a fallback (internal logic)
    if not pkg:
        # We need a session_id for get_package, but get_package_details_summary doesn't need it.
        # Let's use the summary method directly.
        return BookingService.get_package_details_summary(package_name_or_id)
        
    return BookingService.get_package_details_summary(pkg.id)


class VoiceAgent:
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        if not self.api_key:
            logger.warning("GOOGLE_API_KEY not set. Agent will fail to run.")

        # Initialize Session Service (no app_name argument)
        # We keep this global to persist sessions across requests
        # Initialize Session Service (no app_name argument)
        # We keep this global to persist sessions across requests
        self.session_service = InMemorySessionService()
        self.memory_agent = MemoryAgent()
        
        
        # Initialize Duffel Service
        self.duffel_service = DuffelService()
        self.amadeus_service = AmadeusService()

    def process_message(self, user_id: str, session_id: str, message: str, region: str = "UK") -> str:
        """
        Process a text message and return the full text response.
        (Maintains compatibility with non-streaming callers)
        """
        return "".join(list(self.process_message_stream(user_id, session_id, message, region)))

    def process_message_stream(self, user_id: str, session_id: str, message: str, region: str = "UK"):
        """
        Process a text message and yield chunks of the text response as they are generated.
        """
        logger.info(f"Processing message (stream): {message} (Region: {region})")
        
        # Ensure session exists in the session service
        app_name = "voice_bot_app"
        try:
            session = self.session_service.get_session_sync(app_name=app_name, user_id=user_id, session_id=session_id)
            if session is None:
                 logger.info(f"Session {session_id} not found, creating it.")
                 self.session_service.create_session_sync(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception as e:
            logger.warning(f"Error ensuring session: {e}")
        
        # --- ACTIVE MEMORY: Structured Rewrite (Backgrounded) ---
        def run_memory_update():
            try:
                current_profile = ProfileService.get_profile(user_id)
                last_bot_message = "None (Start of conversation)"
                
                try:
                     session_for_mem = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
                     if session_for_mem and session_for_mem.events:
                          for i in range(len(session_for_mem.events) - 1, -1, -1):
                              event = session_for_mem.events[i]
                              if getattr(event, 'author', '') in ['model', 'ray_and_rae'] or getattr(event, 'role', '') == 'model':
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

                logger.info(f"Updating profile background: User='{message}', Bot='{last_bot_message[:50]}...'")
                new_profile = self.memory_agent.update_structured_profile(current_profile, last_bot_message, message)
                ProfileService.update_profile(user_id, new_profile)
                logger.info(f"Background profile update complete for {user_id}")
                
            except Exception as e:
                logger.error(f"Failed to execute background Active Memory update: {e}")

        import threading
        threading.Thread(target=run_memory_update, daemon=True).start()

        # Fetch current profile for the runner (using state BEFORE background update for speed, 
        # or it will be updated by the time the next message comes)
        user_profile = ProfileService.get_profile(user_id)
        
        # Model initialization with streaming enabled
        model = Gemini(model="gemini-2.0-flash", stream=True)
        
        # Tools binding
        def create_package_bound(title: str, package_type: str = "mixed"):
            return create_new_package_tool(session_id, user_id, title, package_type)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None):
            return add_item_to_package_tool(session_id, package_id, item_name, item_type, price, description, image_url, product_url, day, date, rating, review_link, reviews, images)

        def remove_item_bound(package_id: str, item_id: str):
            return remove_item_from_package_tool(session_id, package_id, item_id)

        def save_user_info_bound(fact: str):
            return update_profile_memory_tool(user_id, fact)
        
        def get_package_details_bound(package_name_or_id: str):
            return get_package_details_tool(user_id, package_name_or_id)

        def perform_google_search_bound(query: str):
            return perform_google_search(query, region=region)

        def search_products_bound(query: str):
            return search_products(query, region=region)
            
        def check_amazon_stock_bound(product_name: str, variant_details: str):
            return check_amazon_stock(product_name, variant_details, region=region)
            
        def search_amazon_bound(query: str):
            return search_amazon(query, region=region)

        def search_amazon_with_reviews_bound(query: str):
            return search_amazon_with_reviews(query, region=region)

        def search_flights_duffel(origin: str, destination: str, date: str, end_date: str = None):
            return self.duffel_service.search_flights_formatted(origin, destination, date, end_date)

        def search_hotels_amadeus(city_code_or_name: str, check_in: str, check_out: str):
            target_code = city_code_or_name
            if len(city_code_or_name) > 3 or not city_code_or_name.isupper():
                resolved = self.amadeus_service.resolve_city_to_iata(city_code_or_name)
                if resolved: target_code = resolved
            if len(target_code) == 3 and target_code.isupper():
                result = self.amadeus_service.search_hotels_formatted(target_code)
                if result and "No hotel offers found" not in result and "disabled" not in result:
                     return result
            return search_hotels(city_code_or_name, check_in, check_out)

        def search_activities_amadeus(location: str, keyword: str = ""):
            search_keyword = keyword
            if keyword.lower() in ["family", "kids", "children"]:
                search_keyword = "family friendly"
            amadeus_res = self.amadeus_service.search_activities_formatted(location, search_keyword)
            if "No activities found" not in amadeus_res:
                return amadeus_res
            if search_keyword:
                broad_res = self.amadeus_service.search_activities_formatted(location)
                if "No activities found" not in broad_res:
                    return f"{broad_res}\n(Note: No specific matches for '{keyword}', showing general activities.)"
            query = f"Things to do in {location}"
            if keyword: query = f"{keyword} in {location}"
            google_res = perform_google_search_bound(query)
            return f"{google_res}\n(Note: Amadeus had no specific tours, falling back to Google Search results.)"

        agent = Agent(
            name="ray_and_rae",
            model=model,
            tools=[
                perform_google_search_bound, 
                search_flights_duffel, 
                search_hotels_amadeus,
                search_activities_amadeus,
                search_products_bound, 
                check_amazon_stock_bound, 
                search_amazon_bound, 
                create_package_bound, 
                add_item_bound,
                remove_item_bound,
                save_user_info_bound,
                search_amazon_with_reviews_bound,
                list_user_packages_tool,
                search_packages_tool,
                get_package_details_bound
            ],
            instruction=f"""You are "Ray and Rae", an intelligent AI assistant who acts as a specialized Travel & Shopping Consultant.
            Your goal is to help users plan amazing trips and find the perfect products for their lifestyle.

            ### COMPABILITIES & TOOLS:
            1. **Travel Search**: Use `search_flights_duffel`, `search_hotels_amadeus`, and `search_activities_amadeus` to find travel options.
            2. **Shopping**: Use `search_products_bound`, `search_amazon_bound`, and `search_amazon_with_reviews_bound` to find items.
            3. **Package Management**:
               - Use `list_user_packages_tool` to see a summary of EVERYTHING the user has planned (drafts and booked).
               - Use `search_packages_tool` to find specific packages by title, date (year/month), or type.
               - Use `get_package_details_bound` to see what is INSIDE a specific package (flights, hotels, activities). ALWAYS call this when a user asks to "open", "show", or "summarize" a specific trip/package.
               - Use `create_package_bound` to start a new collection.
               - Use `add_item_bound` to add items (flights, hotels, activities, products) to a package.
               - Use `remove_item_bound` to take things out.
            4. **Memory**: Use `save_user_info_bound` to remember persistent facts about the user.

            ### GUIDELINES:
            - **Brevity**: Keep your spoken responses concise and conversational.
            - **NO SYSTEM IDs**: NEVER mention "ID" or long hexadecimal codes (like 'e5be3a2f...') to the user. Refer to packages by their names (e.g., "the Maldives summer trip").
            - **Package Awareness**: When a user asks "what have you planned for me?" or similar, ALWAYS call `list_user_packages_tool` first to get a current view of their history.
            - **Opening Packages**: When a user says "Open the Maldives trip", call `get_package_details_bound` using the name they provided.
            - **Interactive Options**: Use the `[RESPONSE_OPTIONS]` protocol to provide buttons for choices. 
              Example: `[RESPONSE_OPTIONS] ["Open Maldives Trip", "Search 2024", "Explore Shopping"]`
            - **Product Proposals**: When suggesting products, use the `[PROPOSE_PRODUCTS]` protocol if you have a list of options for them to pick from.
            - **Natural Summaries**: When summarizing multiple packages, be warm and helpful. Instead of a dry list, say something like: "I've got a few things saved for you! We have that Maldives trip from last year and a new shopping draft for beach gear. Which would you like to look at?"

            Current User ID: {user_id}
            Current Session ID: {session_id}
            """
        )
        
        # NOTE: I need to preserve the full instructions. I'll use the existing agent instance or re-inject.
        # For the tool call, I'll be careful to include the full instruction from the previous view_file.
        # Actually, I can just wrap the existing run logic.

        runner = Runner(
            agent=agent,
            app_name="voice_bot_app",
            session_service=self.session_service
        )
        
        from google.genai.types import Content, Part
        msg = Content(role="user", parts=[Part(text=message)])
        
        tool_calls_made = []
        accumulated_text = ""

        try:
            for event in runner.run(user_id=user_id, session_id=session_id, new_message=msg):
                event_author = getattr(event, 'author', None)
                event_role = getattr(event, 'role', None)
                is_model_event = (event_author and event_author != 'user') or (event_role and event_role == 'model') or event_author == 'ray_and_rae'
                
                chunk = ""
                if hasattr(event, 'text') and event.text:
                    if is_model_event or not event_author:
                        chunk = event.text
                
                if not chunk and hasattr(event, 'content') and event.content:
                    if is_model_event or not event_author:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    chunk += part.text
                        elif hasattr(event.content, 'text') and event.content.text:
                            chunk = event.content.text
                
                if chunk:
                    accumulated_text += chunk
                    yield chunk

                if hasattr(event, 'tool_calls') and event.tool_calls:
                    for tc in event.tool_calls:
                        if hasattr(tc, 'name'):
                            tool_calls_made.append(tc.name)

            if not accumulated_text.strip() and tool_calls_made:
                tool_names = ", ".join(set(tool_calls_made))
                yield f"I have executed the following actions: {tool_names}. Is there anything else?"

        except Exception as e:
            logger.error(f"Error running agent stream: {e}", exc_info=True)
            yield f"Error: {str(e)}"

# Global instance
voice_agent = VoiceAgent()
