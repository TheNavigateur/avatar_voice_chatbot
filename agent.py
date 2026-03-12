import os
import json
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
from services.google_places_service import GooglePlacesService
from services.correction_engine import CorrectionEngine
from booking_service import BookingService
from models import PackageItem, PackageType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from profile_service import ProfileService
from memory_agent import MemoryAgent

def clean_location_from_title(title: str) -> str:
    """Helper to extract a clean location name from a package title."""
    if not title: return ""
    import re
    t = title
    # Remove common trip words
    t = re.sub(r'\b(Holiday|Trip|Getaway|Package|Enrichment|Planned|New)\b', '', t, flags=re.IGNORECASE)
    # Remove dates (years like 2027, 2024)
    t = re.sub(r'\b20\d{2}\b', '', t)
    # Remove months
    months = r'\b(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b'
    t = re.sub(months, '', t, flags=re.IGNORECASE)
    # Remove relative timing words
    t = re.sub(r'\b(in|a|months?|weeks?|days?|next)\b', '', t, flags=re.IGNORECASE)
    # Remove isolated numbers (like '4' from 'in 4 months')
    t = re.sub(r'\b\d+\b', '', t)
    # Clean up whitespace
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def _enrich_item_metadata(session_id: str, package_id: str, item: PackageItem, item_name: str, item_type: str, image_url: str = None, images: list = None):
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
            # Extract specific location context from metadata if available (e.g. from Amadeus/Duffel)
            item_city = item.metadata.get('city') or item.metadata.get('location')
            
            # Detect location context from the package title (CLEANED) as a fallback
            fallback_location = ""
            pkg = BookingService.get_package(session_id, package_id)
            if pkg and pkg.title:
                fallback_location = clean_location_from_title(pkg.title)
            
            location = item_city or fallback_location
            
            found_images = []
            if item_type == 'activity':
                found_images = image_service.get_activity_image(item_name, location, num=5)
            elif item_type == 'hotel' or item_type == 'accommodation':
                found_images = image_service.get_hotel_image(item_name, num=5)
            elif item_type == 'flight':
                airline = item.metadata.get('airline')
                found_images = image_service.get_flight_image(airline, num=5)
            elif item_type == 'product':
                found_images = image_service.get_product_image(item_name, num=5)
            else:
                found_images = image_service.search_image_multi(f"{item_name} {location}", num=5)
            
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

    # --- REAL REVIEWS EXTRACTOR ---
    if item_type in ['hotel', 'accommodation', 'activity']:
        try:
            places_service = GooglePlacesService()
            # Use item-specific location context if available, otherwise fallback to title
            item_city = item.metadata.get('city') or item.metadata.get('location')
            fallback_location = ""
            pkg = BookingService.get_package(session_id, package_id)
            if pkg and pkg.title:
                fallback_location = clean_location_from_title(pkg.title)
            
            location = item_city or fallback_location
                
            place_data = places_service.get_place_data(item_name, location)
            if place_data:
                # 1. Update Reviews
                if place_data.get('reviews'):
                    item.metadata['reviews'] = place_data['reviews']
                if place_data.get('review_link'):
                    item.metadata['review_link'] = place_data['review_link']
                
                # 2. Update Photos (PRIORITY over generic search)
                places_images = place_data.get('photos', [])
                if places_images:
                    # For hotels and activities, we want AUTHENTICITY. 
                    # If we found official photos, we PURGE the generic search results.
                    authentic_images = [url for url in places_images if not is_bad_url(url)]
                    if authentic_images:
                        # REPLACING the list instead of appending
                        images = authentic_images
                        item.metadata['images'] = images[:10]
                        item.metadata['image_url'] = images[0]
                        logger.info(f"Purged generic images for '{item_name}' and replaced with {len(authentic_images)} authentic photos.")
        except Exception as e:
            logger.warning(f"Failed to fetch authentic Google reviews for '{item_name}': {e}")

    return item

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
    item = _enrich_item_metadata(session_id, package_id, item, item_name, item_type, image_url, images)
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
    summary += "\n(Note to Agent: The '[SYSTEM_ID: ...]' is for your tool calls ONLY. DO NOT speak or print it in your response. If you want the user to see a package, use the navigation protocol.)\n"
    summary += "Which one would you like to open? Remember to use the ID internally with '[NAVIGATE_TO_PACKAGE: id]' to open it for them."
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

        # Initialize Session Service
        self.session_service = InMemorySessionService()
        self.memory_agent = MemoryAgent()
        
        # Services will be initialized per request or kept if thread-safe
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
            elif event_type == "error":
                logger.error(f"Agent Error during processing: {content}")
                return f"I'm sorry, I encountered an error while processing your request: {content}. Please try again."
        
        if not full_text:
            return "I'm sorry, I couldn't generate a response. Please try asking again."
            
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
        
        # --- PERSONA HELPER ---
        import re
        def format_thinking_persona(text):
            """Ensures meta-logs use 'I' instead of 'Agent' but leaves content for the model to handle naturally."""
            t = str(text)
            # Meta-log adjustments ONLY - do not use regex for 'you' as it breaks grammar
            t = re.sub(r'\bAgent decided to call\b', 'I decided to call', t, flags=re.IGNORECASE)
            t = re.sub(r'\bAgent\b', 'I', t, flags=re.IGNORECASE)
            return t

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

        # Fetch current profile for the runner
        user_profile = ProfileService.get_profile(user_id)
        yield ("thinking", format_thinking_persona(f"Retrieved your profile: {user_profile}"))
        
        # --- LATEST PACKAGE CONTENT CONTEXT (FOR CURRENT VIEW) ---
        package_view_context = ""
        if package_id:
            try:
                yield ("thinking", format_thinking_persona(f"Accessing your current package view context (ID: {package_id})"))
                details = BookingService.get_package_details_summary(package_id)
                if details:
                    package_view_context = f"\nUSER CONTEXT: You are currently viewing the following package details:\n{details}\n\nIf you ask for a summary, details, or 'what's in it', provide a descriptive verbal summary based on these details. Do not say 'the details are on the screen'."
                    yield ("thinking", format_thinking_persona(f"Using your package details: {details}"))
            except Exception as e:
                logger.warning(f"Failed to fetch package context for {package_id}: {e}")
 
        # --- GLOBAL USER CONTEXT (PACKAGES & PROFILE) ---
        all_packages_summary = ""
        try:
            yield ("thinking", format_thinking_persona("Retrieving a summary of all your packages..."))
            all_packages_summary = BookingService.get_user_packages_summary(user_id)
            logger.info(f"Retrieved {len(all_packages_summary)} characters of package summary for {user_id}")
            yield ("thinking", format_thinking_persona(f"Found your existing packages: {all_packages_summary}"))
        except Exception as e:
            logger.warning(f"Failed to fetch all packages summary: {e}")

        global_context = f"""
        ### YOUR LIFESTYLE & PLANNED PACKAGES:
        You have direct access to your saved profile and planned packages. Do not claim you don't know what you have planned.
        
        **Your Profile (About Me):**
        {user_profile or 'No profile information available yet.'}
 
        **Summary of your Current Packages:**
        {all_packages_summary}
        """

        # --- MODEL INITIALIZATION (PER-REQUEST to avoid event loop issues) ---
        from google.adk.models import Gemini
        model = Gemini(model="gemini-2.0-flash", stream=True, api_key=self.api_key)
        
        yield ("thinking", format_thinking_persona("Initializing Agent (Gemini-2.0-Flash)..."))

        # --- TOOL WRAPPER (FOR FIXING STRATEGY) ---
        def run_tool(name: str, func, **kwargs):
            # 1. Apply Correction Rules
            params = kwargs
            try:
                params = CorrectionEngine.apply_corrections(name, kwargs)
            except Exception as e:
                logger.error(f"Correction Engine failed: {e}")
            
            # 2. Execute Tool
            try:
                result = func(**params)
                
                # Check for "soft" failures (e.g. string results indicating no results found)
                # This helps catch failures where the tool returns a string instead of raising an exception
                if isinstance(result, str) and ("No results found" in result or "No bookable hotel offers" in result or "No activities found" in result):
                    CorrectionEngine.record_failure(name, params, f"Soft Failure: {result}", package_id=package_id)
                
                return result
            except Exception as e:
                # 3. Record "Hard" Failure
                error_msg = str(e)
                logger.error(f"Tool {name} failed: {error_msg}")
                CorrectionEngine.record_failure(name, params, error_msg, package_id=package_id)
                
                # Return a safe error message for the agent to pivot
                return f"Error from {name}: {error_msg}. Please pivot to an alternative solution (like Google Search) without telling the user about this error."

        # Tools binding
        def create_package_bound(title: str, package_type: str = "mixed"):
            return run_tool("create_package", create_new_package_tool, session_id=session_id, user_id=user_id, title=title, package_type=package_type)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None):
            return run_tool("add_item", add_item_to_package_tool, session_id=session_id, package_id=package_id, item_name=item_name, item_type=item_type, price=price, description=description, image_url=image_url, product_url=product_url, day=day, date=date, rating=rating, review_link=review_link, reviews=reviews, images=images)

        def remove_item_bound(package_id: str, item_id: str):
            return run_tool("remove_item", remove_item_from_package_tool, session_id=session_id, package_id=package_id, item_id=item_id)

        def save_user_info_bound(fact: str):
            return run_tool("save_user_info", update_profile_memory_tool, user_id=user_id, fact=fact)
        
        def get_package_details_bound(package_name_or_id: str):
            return run_tool("get_package_details", get_package_details_tool, user_id=user_id, package_name_or_id=package_name_or_id)
        def log_reasoning(thought: str):
            """
            Logs a FULL summary of what you are doing to the transparency trace.
            Use this at the start of every turn and before/after tool calls.
            
            CRITICAL PERSONA RULES:
            1. EXTREMELY SHORT: Keep your thought EXTREMELY SHORT (under 10 words if possible) but provide a full summary of what you are doing. Do not just say 'Thinking...'.
            2. WORD BAN: Never use the word "user", "user's", or "the user".
            3. DIRECT ADDRESS: Always address the thought directly to the person you are helping.
            4. USE 2ND PERSON: Use "You", "Your", "You've", "You're".
            5. EXAMPLE: Instead of "The user wants a beach trip", say "You want a beach trip".
            """
            logger.info(f"[LOG_REASONING] Model says: {thought}")
            return thought

        def perform_google_search_bound(query: str):
            return run_tool("google_search", perform_google_search, query=query, region=region)

        def search_products_bound(query: str):
            return run_tool("search_products", search_products, query=query, region=region)
            
        def check_amazon_stock_bound(product_name: str, variant_details: str):
            return run_tool("check_amazon_stock", check_amazon_stock, product_name=product_name, variant_details=variant_details, region=region)
            
        def search_amazon_bound(query: str):
            return run_tool("search_amazon", search_amazon, query=query, region=region)

        def search_amazon_with_reviews_bound(query: str):
            return run_tool("search_amazon_with_reviews", search_amazon_with_reviews, query=query, region=region)

        def search_flights_duffel(origin: str, destination: str, date: str, end_date: str = None):
            def _flight_exec(origin, destination, date, end_date):
                target_origin = origin
                if len(origin) != 3 or not origin.isupper():
                    resolved_origin = self.duffel_service.resolve_place(origin)
                    if resolved_origin: target_origin = resolved_origin
                
                target_destination = destination
                if len(destination) != 3 or not destination.isupper():
                    resolved_destination = self.duffel_service.resolve_place(destination)
                    if resolved_destination: target_destination = resolved_destination
                    
                return self.duffel_service.search_flights_formatted(target_origin, target_destination, date, end_date)
            
            return run_tool("search_flights", _flight_exec, origin=origin, destination=destination, date=date, end_date=end_date)

        def search_hotels_amadeus(city_code_or_name: str = None, check_in: str = None, check_out: str = None, latitude: float = None, longitude: float = None, radius: int = 10):
            return run_tool("search_hotels", self.amadeus_service.search_hotels_formatted, 
                            city_code_or_name=city_code_or_name, check_in=check_in, check_out=check_out, 
                            latitude=latitude, longitude=longitude, radius=radius)

        def search_activities_amadeus(location: str, keyword: str = ""):
            def _activity_exec(location, keyword):
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
                google_res = perform_google_search(query, region=region)
                return f"{google_res}\n(Note: Amadeus had no specific tours, falling back to Google Search results.)"
            
            return run_tool("search_activities", _activity_exec, location=location, keyword=keyword)

        def list_all_packages():
            return run_tool("list_all_packages", list_user_packages_tool, user_id=user_id)
        
        def find_packages(query: str = None, date_filter: str = None, package_type: str = None):
            return run_tool("find_packages", search_packages_tool, user_id=user_id, query=query, date_filter=date_filter, package_type=package_type)

        def delete_package_bound(package_id: str):
            return run_tool("delete_package", BookingService.delete_package, package_id=package_id)

        def propose_itinerary_batch_bound(items_json: str, package_id: str = None):
            """
            Adds a batch of itinerary items to a package in one go.
            Args:
                items_json: A JSON string representing a list of items.
                package_id: (Optional) The specific UUID of the package to add items to. If missing, it uses the latest.
                Each item should have:
                  - name: A SHORT, PROPER TITLE (e.g. "Dreamworld Theme Park", "Noosa Biosphere Reserve Cycle Trail"). NEVER a truncated sentence from the description. Max 6 words.
                  - item_type (flight/hotel/activity/restaurant)
                  - price, description, day (int), date (string), image_url (optional)
                  - time (optional, e.g. "09:00" - the suggested start time for the activity)
                  - duration_hours (optional, float - estimated duration including time at the activity itself, e.g. 3.5 for a half-day tour)
                  - images (optional, list of image URLs)
                  - review_link (optional, string URL to reviews)
                **CRITICAL**: You MUST pass the `package_id` of the specific holiday you are building. This prevents items from being mixed into a different package if the user has multiple holidays planned.
                CRITICAL: The 'name' and 'description' must be completely separate. The description must OPEN with a personalised reason sentence explaining why this was chosen for this specific traveller. 
            """
            try:
                items_data = json.loads(items_json)
                package_items = []
                logger.info(f"Proposing batch of {len(items_data)} items...")
                
                # Use provided package_id or fallback to latest
                active_pkg = None
                if package_id:
                    active_pkg = BookingService.get_package(session_id, package_id)
                
                if not active_pkg:
                    active_pkg = BookingService.get_latest_session_package(session_id)
                
                if not active_pkg:
                    return "Error: No active package found to add items to. Create a package first."
                
                target_package_id = active_pkg.id
                logger.info(f"Adding batch to package: {active_pkg.title} ({target_package_id})")
                
                for data in items_data:
                    item_name = data.get('name') or data.get('title')
                    item_type = data.get('item_type', 'activity')
                    
                    if not item_name:
                        item_name = f"Planned {item_type.capitalize()}"
                    
                    pkg_item = PackageItem(
                        name=item_name,
                        item_type=item_type,
                        price=float(data.get('price', 0.0)),
                        description=data.get('description', '')
                    )
                    # Merge additional metadata
                    pkg_item.metadata.update({
                        'day': data.get('day'),
                        'date': data.get('date'),
                        'image_url': data.get('image_url'),
                        'images': data.get('images', []),
                        'product_url': data.get('product_url'),
                        'rating': data.get('rating'),
                        'reviews': [], # Blanked. We fetch authentic ones below.
                        'review_link': data.get('review_link'),
                        'time': data.get('time'),
                        'duration_hours': data.get('duration_hours')
                    })
                    
                    # Enrich automatically fetched images & real Google Places Reviews
                    try:
                        pkg_item = _enrich_item_metadata(session_id, target_package_id, pkg_item, item_name, item_type, data.get('image_url'), data.get('images', []))
                    except Exception as enrichment_err:
                        logger.warning(f"Metadata enrichment failed for {item_name}: {enrichment_err}")
                    
                    package_items.append(pkg_item)
                
                if not package_items:
                    return "No valid items were found in the provided batch."

                res = BookingService.add_items_to_package(session_id, target_package_id, package_items)
                return f"Successfully added {len(package_items)} items to package '{active_pkg.title}' ({target_package_id})."
            except Exception as e:
                logger.error(f"Error in propose_itinerary_batch_bound: {e}")
                return f"Error adding batch items: {str(e)}"

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
                log_reasoning,
                propose_itinerary_batch_bound
            ],
            instruction=f"""
            ### -1. TODAY'S DATE (GROUND TRUTH — HIGHEST PRIORITY):
            - **TODAY IS: {current_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**. This is the single authoritative source of truth for the current date and time.
            - When a traveller says "in 2 weeks", "next month", "this summer", or any relative date phrase, you MUST calculate it from TODAY'S DATE above.
            - **CRITICAL**: Existing packages in your context are FUTURE PLANS, not the current date. Their travel dates (e.g. 2027) are trip dates, NOT today's date.

            ### 0. DISCOVERY & SELECTION PROTOCOLS (Level 6 & 7):
            - **Phase 0 (Triage)**: Mandatory check if New or Continuing. Create NEW package via `create_package_bound` if vision/intent has changed.
            - **Phase 1 (Logistics)**: Confirm Origin, Duration, and Travel Month.
            - **Phase 2 (Budget)**: Establish clear budget range.
            - **Phase 3 (Soulful Discovery)**: Ask about "Vibe", "Pace", and specific "Activities".
            - **Phase 3.5 (Group & Rhythm)**: Establish WHO is traveling and their SLEEP/WAKE RHYTHM.
            - **Phase 4 (Silent Selection)**: Internally select "Anchor Spot" based on weather and vision. Call `search_hotels_amadeus` or `perform_google_search_bound`.
            - **Phase 6 (Instantaneous Silent Build)**: Build the ENTIRE holiday in one turn using `propose_itinerary_batch_bound`.

            ### 1. THINKING TRANSPARENCY:
            - You MUST call `log_reasoning` as the VERY FIRST tool at the start of EVERY turn.
            - **STRICT PERSONA (2nd Person)**: In `log_reasoning`, you MUST refer to the human as "You".
            - **WORD BAN**: You are STRICTLY FORBIDDEN from using the word "user", "the user", or "user's" in your logs.

            ### 2. SILENT ACTION MANDATE (CRITICAL):
            - **NO NARRATION**: NEVER narrate your tool uses, actions, or status (e.g., "I've created a package", "I'm adding...", "I am searching for...").
            - **BANNED PHRASES**: Never say "I've created a package", "I've added...", "I'm searching for...", "I've found...", "Looking at...", "Let me just...".
            - **DISCOVERY SPEECH PROTOCOL (Phases 1-4)**: Your speech MUST consist ONLY of discovery questions, sensory descriptions, or vibe-setting. NEVER report on what you have just done with your tools. The user should only see the results in the UI, never hear about the process.
            - **NO FAILURE NARRATION**: If a tool fails or you have trouble finding something, NEVER tell the traveller. SILENTLY pivot to an alternative (e.g., Google Search if Amadeus fails) or add a best-estimate manually. The traveller should never hear about your "trouble".
            - **DEFERRAL BAN**: NEVER say "I will work on it", "I'll build it for you", or "I'm doing that now". Instead, just DO it immediately in the same turn.
            - **SILENT BUILD**: Execute `propose_itinerary_batch_bound` IMMEDIATELY once requirements are met. Do NOT ask for permission to build.

            ### 3. DESTINATION & ID SECRECY:
            - **ANONYMITY**: NEVER name any specific location, city, or hotel in speech until the hotel has been added to the package (`add_item_bound`). Use evocative sensory descriptions instead.
            - **THE "WHERE" BAN**: NEVER ask the traveller for a destination preference. The selection is yours to make silently.
            - **PACKAGE ID SECRECY**: NEVER speak or print Package IDs (UUIDs).

            ### 4. IDENTITY & UI:
            - Use "{avatar_name or 'Ray and Rae'}", use "we" for the service.
            - **END WITH A QUESTION**: Every speech response MUST end with a question to move the activity forward.
            - **MANDATED RESPONSE (After Build)**: Once you have successfully called `propose_itinerary_batch_bound`, your response MUST be: "I've built out your full holiday plan for you to review in the package view. Let me know if you'd like me to change anything."
            - **NAVIGATE**: ALWAYS append `[NAVIGATE_TO_PACKAGE: package_id]` after your speech whenever a build is complete.

            ### 5. CONSTRAINTS (SANDWICH ENFORCEMENT - BOTTOM):
            - **HARD BAN**: Never narrate tools or say "I am working on it".
            - **HARD BAN**: Never tell the traveller you are "having trouble" or "finding it difficult". Just find a workaround silently.
            - **HARD BAN**: No location names in speech during Phases 1–4.
            - **HARD BAN**: Never ask "Where?".
            - **PROACTIVITY**: If you have enough info to build, BUILD NOW. Do not ask "Would you like me to build it?".

            ### 6. LOGICAL CONSISTENCY & CLIMATE SAFETY:
            - **Non-Negotiable Activity Climate Table**:
                | Activity | Required Climate |
                | :--- | :--- |
                | Skiing, Snowboarding | COLD (Below 5°C / 41°F) |
                | Ice Skating (Outdoor) | COLD (Below 5°C / 41°F) |
                | Beach, Swimming (Outdoor) | WARM (Above 22°C / 72°F) |
                | Water Parks | WARM (Above 22°C / 72°F) |
                | Desert Safari | HOT (Above 25°C / 77°F) |
            - **Mandate**: NEVER combine items from this table with an incompatible climate description or month. 
            - **Conflict Resolution**: If a user's profile or previous message creates a conflict (e.g., "Warm weather" + "Skiing"), you MUST NOT proceed with both. Instead, politely point out the contradiction or ask which they'd like to prioritize. 
            - **Example**: "I see you're interested in skiing, which typically needs a colder climate. Should we look for a winter destination, or stick with a warm-weather trip and find some different adventures?"

            {package_view_context}
            {global_context}

            ### FINAL MANDATES (RECAP - TOP PRIORITY):
            - **CRITICAL**: Use `[NAVIGATE_TO_PACKAGE: package_id]` to open the holiday/package view at the end of every build or upon request.
            - **CRITICAL**: Never narrate your actions in speech (e.g. "I have created a package", "I am adding...", "I am working on it", "I need to create a package for you"). Actions like creating an itinerary must be done silently using tools immediately in the same turn.
            - **CRITICAL**: Never speak or print Package IDs (UUIDs).
            - **CRITICAL**: No location names during discovery (Phases 1–4). Once the hotel is added, you may name the destination freely.
            - **CRITICAL**: NEVER say you have "booked" something. You are proposing a package. Use "added".
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
                                yield ("thinking", format_thinking_persona(f"LOG: {thought}"))
                            else:
                                yield ("thinking", format_thinking_persona(f"I decided to call: {tool_called}({tool_args})"))
                        
                        # Check for function_response (tool returning data)
                        fr = getattr(part, 'function_response', None)
                        if fr:
                            res_val = getattr(fr, 'response', {})
                            # Often response is a dict with 'result' or similar
                            res_str = str(res_val.get('result', res_val)) if isinstance(res_val, dict) else str(res_val)
                            yield ("thinking", format_thinking_persona(f"Tool returned: {res_str}"))
 
                # Fallback for events that have .tool_calls directly (older ADK or different event types)
                tool_calls = getattr(event, 'tool_calls', None)
                if tool_calls:
                    for tc in tool_calls:
                        tool_called = getattr(tc, 'name', 'unknown')
                        tool_args = getattr(tc, 'args', {})
                        if tool_called == "log_reasoning":
                            thought = tool_args.get("thought", "")
                            yield ("thinking", format_thinking_persona(f"LOG: {thought}"))
                        else:
                            yield ("thinking", format_thinking_persona(f"I decided to call: {tool_called}({tool_args})"))
 
                tool_outputs = getattr(event, 'tool_outputs', None)
                if tool_outputs:
                    for to in tool_outputs:
                         res_summary = str(getattr(to, 'content', ''))
                         yield ("thinking", format_thinking_persona(f"Tool outcome: {res_summary}"))

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
