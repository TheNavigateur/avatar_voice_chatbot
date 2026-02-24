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
        # Simple date extraction
        pkg_date = "No dates set"
        for item in p.items:
            d = item.metadata.get('date') or item.metadata.get('check_in')
            if d:
                pkg_date = d
                break
        
        summary += f"- '{p.title}' [SYSTEM_ID: {p.id}] Status: {p.status.value.capitalize()}, Date: {pkg_date}\n"
    summary += "\n(Note to Agent: The '[SYSTEM_ID: ...]' is for your tool calls ONLY. DO NOT speak or print it in your response.)\n"
    summary += "Which one would you like to open? Remember to use the ID internally."
    return summary

def get_package_details_tool(user_id: str, package_name_or_id: str):
    """
    Returns full details of a package (its items) by name or ID.
    Args:
        user_id: The current user ID.
        package_name_or_id: The name/title of the package (e.g., 'Maldives Trip') or its unique ID.
    """
    logger.info(f"[TOOL] Getting package details for: {package_name_or_id}")
    
    # If it looks like a UUID, use it directly
    if len(package_name_or_id) > 20 and '-' in package_name_or_id:
         return BookingService.get_package_details_summary(package_name_or_id)

    # Try by title
    pkg = BookingService.get_package_by_title(user_id, package_name_or_id)
    if pkg:
        return BookingService.get_package_details_summary(pkg.id)
        
    return BookingService.get_package_details_summary(package_name_or_id)


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

    def process_message(self, user_id: str, session_id: str, message: str, region: str = "UK", package_id: str = None, avatar_name: str = None, current_time: str = None) -> str:
        """
        Process a text message and return the full text response.
        (Maintains compatibility with non-streaming callers)
        """
        full_text = []
        for event_type, content in self.process_message_stream(user_id, session_id, message, region, package_id, avatar_name, current_time):
            if event_type == "text":
                full_text.append(content)
        return "".join(full_text)

    def process_message_stream(self, user_id: str, session_id: str, message: str, region: str = "UK", package_id: str = None, avatar_name: str = None, current_time: str = None):
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
        # Fetch current profile for the runner
        user_profile = ProfileService.get_profile(user_id)
        yield ("thinking", f"Retrieved User Profile for {user_id}: {user_profile[:200]}...")
        
        # --- LATEST PACKAGE CONTENT CONTEXT (FOR CURRENT VIEW) ---
        package_view_context = ""
        if package_id:
            try:
                yield ("thinking", f"Accessing current package view context for ID: {package_id}")
                details = BookingService.get_package_details_summary(package_id)
                if details:
                    package_view_context = f"\nUSER CONTEXT: The user is currently viewing the following package details:\n{details}\n\nIf the user asks for a summary, details, or 'what's in it', you should provide a descriptive verbal summary based on these details. You no longer need to say 'the details are on the screen'."
                    yield ("thinking", f"Using Package Context: {details[:200]}...")
            except Exception as e:
                logger.warning(f"Failed to fetch package context for {package_id}: {e}")

        # --- GLOBAL USER CONTEXT (PACKAGES & PROFILE) ---
        all_packages_summary = ""
        try:
            yield ("thinking", "Retrieving summary of all user packages...")
            all_packages_summary = BookingService.get_user_packages_summary(user_id)
            logger.info(f"Retrieved {len(all_packages_summary)} characters of package summary for {user_id}")
            yield ("thinking", f"Found existing packages: {all_packages_summary[:200]}...")
        except Exception as e:
            logger.warning(f"Failed to fetch all packages summary: {e}")

        global_context = f"""
        ### USER LIFESTYLE & PLANNED PACKAGES:
        You have direct access to the user's saved profile and planned packages. Do not claim you don't know what they have planned.
        
        **User Profile (About Me):**
        {user_profile or 'No profile information available yet.'}

        **Current Packages Summary:**
        {all_packages_summary}
        """

        # Model initialization with streaming enabled
        model = Gemini(model="gemini-2.0-flash", stream=True, api_key=self.api_key)
        
        yield ("thinking", "Initializing Agent (Gemini-2.0-Flash)...")

        # Tools binding
        def create_package_bound(title: str, package_type: str = "mixed"):
            # yield_thinking(f"Tool Call: create_package_bound(title='{title}', type='{package_type}')") # Handled by runner.run loop
            res = create_new_package_tool(session_id, user_id, title, package_type)
            # yield_thinking(f"Tool Result: {res}") # Handled by runner.run loop
            return res
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None):
            # yield_thinking(f"Tool Call: add_item_bound(item='{item_name}', type='{item_type}', package='{package_id}')") # Handled by runner.run loop
            res = add_item_to_package_tool(session_id, package_id, item_name, item_type, price, description, image_url, product_url, day, date, rating, review_link, reviews, images)
            # yield_thinking(f"Tool Result: Added {item_name}") # Handled by runner.run loop
            return res

        def remove_item_bound(package_id: str, item_id: str):
            # yield_thinking(f"Tool Call: remove_item_from_package(item='{item_id}', package='{package_id}')") # Handled by runner.run loop
            res = remove_item_from_package_tool(session_id, package_id, item_id)
            # yield_thinking(f"Tool Result: {res}") # Handled by runner.run loop
            return res

        def save_user_info_bound(fact: str):
            # yield_thinking(f"Tool Call: save_user_info(fact='{fact}')") # Handled by runner.run loop
            res = update_profile_memory_tool(user_id, fact)
            # yield_thinking(f"Tool Result: {res}") # Handled by runner.run loop
            return res
        
        def get_package_details_bound(package_name_or_id: str):
            # yield_thinking(f"Tool Call: get_package_details(query='{package_name_or_id}')") # Handled by runner.run loop
            res = get_package_details_tool(user_id, package_name_or_id)
            # yield_thinking(f"Tool Result: Retrieved details for {package_name_or_id}") # Handled by runner.run loop
            return res

        def log_reasoning(thought: str):
            """
            Logs internal reasoning, logic, and planning steps to the transparency trace.
            Use this at the start of every turn and before/after tool calls to explain your process.
            This information is ONLY visible in the 'Thinking' trace, NOT in your speech.
            """
            logger.info(f"[LOG_REASONING] Model says: {thought}")
            return f"Reasoning logged: {thought}"

        def perform_google_search_bound(query: str):
            # yield_thinking(f"Tool Call: perform_google_search(query='{query}')") # Handled by runner.run loop
            res = perform_google_search(query, region=region)
            # yield_thinking(f"Tool Result: Search returned {len(res)} results.") # Handled by runner.run loop
            return res

        def search_products_bound(query: str):
            # yield_thinking(f"Tool Call: search_products(query='{query}')") # Handled by runner.run loop
            res = search_products(query, region=region)
            # yield_thinking(f"Tool Result: Found {res.count('Title:') if hasattr(res, 'count') else 'multiple'} products.") # Handled by runner.run loop
            return res
            
        def check_amazon_stock_bound(product_name: str, variant_details: str):
            # yield_thinking(f"Tool Call: check_amazon_stock(product='{product_name}')") # Handled by runner.run loop
            res = check_amazon_stock(product_name, variant_details, region=region)
            # yield_thinking(f"Tool Result: {res}") # Handled by runner.run loop
            return res
            
        def search_amazon_bound(query: str):
            # yield_thinking(f"Tool Call: search_amazon(query='{query}')") # Handled by runner.run loop
            res = search_amazon(query, region=region)
            # yield_thinking(f"Tool Result: Found Amazon listings.") # Handled by runner.run loop
            return res

        def search_amazon_with_reviews_bound(query: str):
            # yield_thinking(f"Tool Call: search_amazon_with_reviews(query='{query}')") # Handled by runner.run loop
            res = search_amazon_with_reviews(query, region=region)
            # yield_thinking(f"Tool Result: Found listings with reviews.") # Handled by runner.run loop
            return res

        def search_flights_duffel(origin: str, destination: str, date: str, end_date: str = None):
            # yield_thinking(f"Tool Call: search_flights_duffel(from='{origin}', to='{destination}', on='{date}')") # Handled by runner.run loop
            if not origin or not destination or not date:
                return "Error: Origin, destination, and date are required for flight search."
            
            target_origin = origin
            if len(origin) != 3 or not origin.isupper():
                resolved_origin = self.duffel_service.resolve_place(origin)
                if resolved_origin: target_origin = resolved_origin
            
            target_destination = destination
            if len(destination) != 3 or not destination.isupper():
                resolved_destination = self.duffel_service.resolve_place(destination)
                if resolved_destination: target_destination = resolved_destination
                
            res = self.duffel_service.search_flights_formatted(target_origin, target_destination, date, end_date)
            # yield_thinking(f"Tool Result: Found flight options.") # Handled by runner.run loop
            return res

        def search_hotels_amadeus(city_code_or_name: str = None, check_in: str = None, check_out: str = None, latitude: float = None, longitude: float = None, radius: int = 10):
            """
            Search for bookable hotel offers via Amadeus API.
            Supports searching by City Code (e.g., 'MLE') or specific coordinates (latitude/longitude).
            """
            res = self.amadeus_service.search_hotels_formatted(
                city_code_or_name=city_code_or_name,
                check_in=check_in,
                check_out=check_out,
                latitude=latitude,
                longitude=longitude,
                radius=radius
            )
            return res

        def search_activities_amadeus(location: str, keyword: str = ""):
            # yield_thinking(f"Tool Call: search_activities_amadeus(at='{location}', keyword='{keyword}')") # Handled by runner.run loop
            search_keyword = keyword
            if keyword.lower() in ["family", "kids", "children"]:
                search_keyword = "family friendly"
            amadeus_res = self.amadeus_service.search_activities_formatted(location, search_keyword)
            if "No activities found" not in amadeus_res:
                # yield_thinking(f"Tool Result: Found activities via Amadeus.") # Handled by runner.run loop
                return amadeus_res
            if search_keyword:
                broad_res = self.amadeus_service.search_activities_formatted(location)
                if "No activities found" not in broad_res:
                    # yield_thinking(f"Tool Result: Found activities via Amadeus (broad).") # Handled by runner.run loop
                    return f"{broad_res}\n(Note: No specific matches for '{keyword}', showing general activities.)"
            query = f"Things to do in {location}"
            if keyword: query = f"{keyword} in {location}"
            google_res = perform_google_search_bound(query)
            # yield_thinking(f"Tool Result: Found activities via Google Search.") # Handled by runner.run loop
            return f"{google_res}\n(Note: Amadeus had no specific tours, falling back to Google Search results.)"

        def list_all_packages():
            # yield_thinking("Tool Call: list_all_packages") # Handled by runner.run loop
            res = list_user_packages_tool(user_id)
            # yield_thinking(f"Tool Result: Found {res.count('-') if hasattr(res, 'count') else 'multiple'} packages.") # Handled by runner.run loop
            return res
        
        def find_packages(query: str = None, date_filter: str = None, package_type: str = None):
            # yield_thinking(f"Tool Call: find_packages(query='{query}')") # Handled by runner.run loop
            res = search_packages_tool(user_id, query, date_filter, package_type)
            # yield_thinking(f"Tool Result: Found matching packages.") # Handled by runner.run loop
            return res

        def delete_package_bound(package_id: str):
            # yield_thinking(f"Tool Call: delete_package(id='{package_id}')") # Handled by runner.run loop
            res = BookingService.delete_package(package_id) or f"Deleted package {package_id}."
            # yield_thinking(f"Tool Result: {res}") # Handled by runner.run loop
            return res

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
                list_all_packages,
                find_packages,
                get_package_details_bound,
                delete_package_bound,
                log_reasoning
            ],
            instruction=f"""
            ### CRITICAL MANDATES (SANDWICH ENFORCEMENT - TOP):
            1. **Thinking Transparency (MANDATORY)**: You MUST call `log_reasoning` as the VERY FIRST tool at the start of EVERY turn. Explain your current phase, your logic, and your next steps.
            2. **Consultant Selection Logic**:
                - **Resilient Tool Use**: If `search_hotels_amadeus` or `search_flights_duffel` returns no results, you MUST NOT give up. You MUST use `perform_google_search_bound` to find specific names, locations, and estimated prices for hotels/flights. Then, you MUST call `add_item_bound` with these estimated details. "Sensory descriptions" are a supplement, NOT a replacement for adding items to the package.
                - **Package Persistence**: Once a package is created or identified in the `Current Packages Summary`, you MUST use its `SYSTEM_ID` for all subsequent `add_item_bound` calls. Do not re-verify the name or re-create it.
                - **Redundancy Reduction**: If the user has already confirmed duration, origin, or budget (even in a previous turn or during a "New Package" flow), do NOT ask again. Proceed directly to the next phase.
                - **Zero-Assumption Basis**: Each new holiday starts as a blank slate for logistics. However, once the user *provides* those logistics, they are "locked in" for that session.
                - **Weather-Experience Alignment**: For experiences like "Water Parks" or "Beaches," you MUST ensure the destination has a high probability of hot weather (28°C+). If the verified temperature is too low (e.g., 20°C in Tenerife in Feb), you MUST explicitly reject it in your reasoning and search elsewhere.
                - **Explicit Weather Discovery**: If the vision is compatible with multiple climates, or if unsure, you MUST ask: "Are you looking for that intense tropical heat, or something a bit more temperate?"
                - **Anchor Proximity**: The `log_reasoning` call MUST list 2-3 discarded candidates and explain why the "Winner" was selected (specifically citing distance from the experience anchor spot).
            3. **Absolute Anonymity (ZERO TOLERANCE)**: You are FORBIDDEN from naming the destination, city, region, or specific hotel in your verbal speech. If asked, refuse to say.
            4. **Conversational Flow**: ALWAYS end your response with a question to move the discovery forward.
            5. **Silence**: Never narrate process or tool usage in speech.

            ### IDENTITY & GOAL:
            You are "{avatar_name or 'Ray and Rae'}", a specialized Travel & Shopping Consultant.
            Use "we" for the service. Your goal is a multi-day surprise itinerary built one day at a time.
  
            ### TOOLS:
            `search_flights_duffel`, `search_hotels_amadeus`, `search_activities_amadeus`, `create_package_bound`, `add_item_bound`, `perform_google_search_bound`, `log_reasoning`.
 
            ### STEALTH DISCOVERY WORKFLOW:
            {package_view_context}
            {global_context}

            1. **Phase 0 (Triage)**: Mandatory check if New or Continuing.
            2. **Phase 1 (Logistics)**: Confirm Origin and Duration. **CRITICAL**: Do NOT ask again if already confirmed in the `Current Packages Summary` or earlier in the chat.
            3. **Phase 2 (Budget)**: Establish clear budget range. **CRITICAL**: If the user has already confirmed a budget, skip this and proceed to Phase 3.
            4. **Phase 3 (Stealth Deep Discovery & Experience-Weather Anchor)**: 
                - Use evocative questions to uncover the user's desired "soulful" experiences.
                - **Weather Discovery**: If the vision could be enjoyed in different climates, or if you're unsure, ASK the user about their weather preference.
                - **Climate Check**: Call `perform_google_search_bound` to verify the destination's climate for the given dates aligns with the requested experience (e.g., "hot weather for beaches").
                - Use `log_reasoning` to EXPLICITLY name and coordinate-map these experiences to an internally identified "ideal spot" after weather verification.
            5. **Phase 4 (Hotel Selection)**:
                - Call `search_hotels_amadeus` with specific coordinates and dates.
                - **API RESILIENCE**: If the API returns no results, you MUST call `perform_google_search_bound` to find specific hotel names, ratings, and prices in that area.
                - LOG reasoning with comparison.
                - Add the selected sanctuary to the package SILENTLY using `add_item_bound`.
            6. **Phase 4.5 (Flight Selection)**:
                - Identify the nearest airport.
                - Search for flights. If API returns nothing, use `perform_google_search_bound` for options/prices.
                - Add the best logistical support to the package SILENTLY using `add_item_bound`.
            7. **Phase 5 (Reveal & Sensory)**: Describe the SENSORY experience for Day 1 (Sensory only, NO NAMES).

            ### CRITICAL NEGATIVE CONSTRAINTS (SANDWICH ENFORCEMENT - BOTTOM):
            - **NO DESTINATION NAMES**: Bali, Paris, London, etc., are BANNED from speech.
            - **BUDGET & VISION FIRST**: Never anchor before Phase 2 & 3.
            - **HIGH QUALITY ONLY**: Always justify your choice as the premier option in the log.
            - **END WITH A QUESTION**: Every speech response MUST end with a question (CTA).
            - **REASONING FIRST**: Call `log_reasoning` before anything else.
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
        
        # Helper to yield thinking events from within tools
        # We need to bridge the gap between tools and the generator
        # Since tools are called synchronously by the runner, we can't easily yield from them directly
        # without changing the ADK. But we can use a queue or just log it for now?
        # Actually, let's just use the 'thinking' events we already have.
        # But wait, how do I get the tool calls *as they happen* into the stream?
        # The runner.run loop catches tool calls.
        
        # We can pass a callback to our tools if we want, but better to handle it in the loop.
        
        from google.genai.types import Content, Part
        msg = Content(role="user", parts=[Part(text=message)])
        
        # The yield_thinking helper function is not needed here as the runner.run loop
        # will handle yielding 'thinking' events for tool calls and outputs.
        # The instruction's proposed yield_thinking inside each tool function won't work
        # directly as `yield` can only be used in a generator function.
        # The ADK's runner.run already yields tool_calls and tool_outputs events.
        # We will process those events in the main loop.
        def yield_thinking(txt):
             pass # This placeholder is no longer needed.

        try:
            for event in runner.run(user_id=user_id, session_id=session_id, new_message=msg):
                # Broadly check for tool interactions in the event
                # ADK/Gemini 2.0 uses function_call and function_response
                content = getattr(event, 'content', None)
                if content:
                    parts = getattr(content, 'parts', [])
                    for part in parts:
                        # Check for function_call (model requesting a tool)
                        fc = getattr(part, 'function_call', None)
                        if fc:
                            tool_called = getattr(fc, 'name', 'unknown')
                            tool_args = getattr(fc, 'args', {})
                            if tool_called == "log_reasoning":
                                thought = tool_args.get("thought", "")
                                yield ("thinking", f"LOG: {thought}")
                            else:
                                yield ("thinking", f"Agent decided to call: {tool_called}({tool_args})")
                        
                        # Check for function_response (tool returning data)
                        fr = getattr(part, 'function_response', None)
                        if fr:
                            res_val = getattr(fr, 'response', {})
                            # Often response is a dict with 'result' or similar
                            res_str = str(res_val.get('result', res_val)) if isinstance(res_val, dict) else str(res_val)
                            yield ("thinking", f"Tool returned: {res_str[:200]}...")

                # Fallback for events that have .tool_calls directly (older ADK or different event types)
                tool_calls = getattr(event, 'tool_calls', None)
                if tool_calls:
                    for tc in tool_calls:
                        tool_called = getattr(tc, 'name', 'unknown')
                        tool_args = getattr(tc, 'args', {})
                        if tool_called == "log_reasoning":
                            thought = tool_args.get("thought", "")
                            yield ("thinking", f"LOG: {thought}")
                        else:
                            yield ("thinking", f"Agent decided to call: {tool_called}({tool_args})")

                tool_outputs = getattr(event, 'tool_outputs', None)
                if tool_outputs:
                    for to in tool_outputs:
                         res_summary = str(getattr(to, 'content', ''))[:200]
                         yield ("thinking", f"Tool returned: {res_summary}...")

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
                    yield ("text", chunk)

        except Exception as e:
            logger.error(f"Error running agent stream: {e}", exc_info=True)
            yield ("error", str(e))

# Global instance
voice_agent = VoiceAgent()
