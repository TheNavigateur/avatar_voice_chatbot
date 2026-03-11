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

        # Model initialization with streaming enabled
        model = Gemini(model="gemini-2.0-flash", stream=True, api_key=self.api_key)
        
        yield ("thinking", format_thinking_persona("Initializing Agent (Gemini-2.0-Flash)..."))

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

        def propose_itinerary_batch_bound(items_json: str):
            """
            Adds a batch of itinerary items to a package in one go.
            Args:
                items_json: A JSON string representing a list of items.
                Each item should have:
                  - name: A SHORT, PROPER TITLE (e.g. "Dreamworld Theme Park", "Noosa Biosphere Reserve Cycle Trail"). NEVER a truncated sentence from the description. Max 6 words.
                  - item_type (flight/hotel/activity/restaurant)
                  - price, description, day (int), date (string), image_url (optional)
                  - time (optional, e.g. "09:00" - the suggested start time for the activity)
                  - duration_hours (optional, float - estimated duration including time at the activity itself, e.g. 3.5 for a half-day tour)
                  - images (optional, list of image URLs)
                  - review_link (optional, string URL to reviews)
                CRITICAL: The 'name' and 'description' must be completely separate. The description must OPEN with a personalised reason sentence explaining why this was chosen for this specific traveller. 
            """
            try:
                items_data = json.loads(items_json)
                package_items = []
                
                # Fetch latest package if package_id is not explicitly provided or known
                active_pkg = BookingService.get_latest_session_package(session_id)
                if not active_pkg:
                    return "Error: No active package found to add items to. Create a package first."
                
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
                    pkg_item = _enrich_item_metadata(session_id, active_pkg.id, pkg_item, item_name, item_type, data.get('image_url'), data.get('images', []))
                    
                    package_items.append(pkg_item)
                
                res = BookingService.add_items_to_package(session_id, active_pkg.id, package_items)
                return f"Successfully added {len(package_items)} items to package '{active_pkg.title}'."
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
            - When a traveller says "in 2 weeks", "next month", "this summer", or any relative date phrase, you MUST calculate it from TODAY'S DATE above — never from a package date.
            - **CRITICAL**: Existing packages in your context are FUTURE PLANS, not the current date. Their travel dates (e.g. 2027) are trip dates, NOT today's date. Do NOT use them to infer what year or month it currently is.
            - If asked to create a trip "in 2 weeks", that departure date = TODAY + 14 days. Use TODAY'S DATE to compute this.

            ### 0. DESTINATION SECRECY & ID SECRECY (MANDATORY):
            - **BEFORE SELECTION — NO DESTINATION NAMES**: During discovery and selection (Phases 1–4), you are STRICTLY FORBIDDEN from naming any destination, city, region, or hotel in your verbal speech. Use evocative sensory descriptions instead (e.g., "that tropical northern coastline", "coral-filled islands").
            - **AFTER SELECTION — REVEAL IS ALLOWED**: Once you have committed to a hotel/destination by calling `add_item_bound` or `propose_itinerary_batch_bound`, you MAY name the destination and hotel naturally in conversation. At that point the location is chosen and the traveller deserves to know where they are going.
            - **THE "WHERE" BAN (discovery only)**: During Phases 1–4, NEVER ask the traveller for a destination or city preference. Never ask "Are you interested in [Location]?". The selection is yours to make silently.
            - **PACKAGE ID SECRECY**: NEVER speak, print, or mention any Package IDs (UUIDs) to the traveller. These are for your internal tool use and navigation commands ONLY.
            - **TERMINOLOGY BAN (BOOKING)**: You are a travel planner creating a *proposed itinerary*, NOT a travel agent making actual bookings. You MUST NEVER say you have "booked" something. Use terms like "added to your package", "selected", or "included in your itinerary". NEVER claim you have booked a hotel, flight, or activity.
            - **REAL DATA MANDATE**: Do NOT hallucinate names of hotels, flights, or activities. You **MUST** call `search_flights_duffel` and `search_hotels_amadeus` (or `search_activities_amadeus`) to find real, bookable options before calling `propose_itinerary_batch_bound`. If you call the batch tool with fake names like "Flight to Gold Coast" instead of "Jetstar JQ123", you have FAILED.
            - **NO DEFERRING (DO IT NOW)**: You correspond in real-time. NEVER say things like "I will work on it now", "I am building it in the background", or "I will do that for you". Instead, simply EXECUTE the necessary tool calls (e.g., `propose_itinerary_batch_bound`) IMMEDIATELY in the same turn and present the finished result.
            - **SELF-CORRECTION**: Before speaking during discovery, verify: "Have I named a location before confirming the booking?" If yes and booking isn't done yet, rewrite to remove it.
            
            ### 1. SEASONAL INTEGRITY & FRESH DISCOVERY (MANDATORY):
            - **FRESH ACTIVITY DISCOVERY**: For EVERY new package, you MUST discover the user's vision (vibe, activities, pace) from scratch. Do NOT blindly assume preferences from the "About Me" or past packages.
            - **FRESH GROUP COMPOSITION**: For EVERY new trip, you MUST ask who is travelling — never assume. Even if a previous trip included children, partners, or elderly relatives, those people may NOT be coming on this trip. If you see past group info, you may use it as a soft prompt only (e.g., "Last time you travelled with the kids — is that the same for this one?"), but NEVER silently carry it over. The group composition must be confirmed explicitly for each new trip.
            - **DOUBLE-CHECK PROTOCOL**: You may use past data ONLY for verification (e.g., "I see you've loved tropical heat before; is that still the case for this trip?"). Never silently assume.
            - **FRESH WEATHER CHECK**: Every new package creation MUST undergo a fresh weather verification for the *specific* intended month via `perform_google_search_bound`. 
            - **NO LAZY REUSE**: Do NOT assume a previous location (e.g., Queensland) is suitable for a different month. Climate varies significantly. 
            - **RE-VALIDATION**: If you see a previous location in context, you MUST re-validate its temperature and rainfall for the *new* month before even considering it as a suggestion. 

            ### 1. THINKING TRANSPARENCY:
            - You MUST call `log_reasoning` as the VERY FIRST tool at the start of EVERY turn. Explain your current phase, your logic, and your discard/winner selection process.
            - **STRICT PERSONA (2nd Person)**: In your reasoning logs (`log_reasoning`), you MUST refer to the human as "You".
            - **WORD BAN**: You are STRICTLY FORBIDDEN from using the word "user", "the user", or "user's" in your logs. 
            - **GRAMMAR**: Use normal 2nd person grammar (e.g., "I see you ARE looking for..." or "I'm checking YOUR profile").
            - **BEFORE vs AFTER**: 
                - WRONG: "I will check the user's profile to see their history."
                - RIGHT: "I will check your profile to see your history."
                - WRONG: "The user is asking for a quiet beach."
                - RIGHT: "You are asking for a quiet beach."

            ### 2. DISCOVERY & SELECTION PROTOCOLS:
            - **SILENT ACTIONS (MANDATORY)**: Never narrate your tool uses or say what you just did (e.g. "I've created a new package called X", "I've added the flight"). Just perform the action silently and immediately ask the next discovery question to move the conversation forward.
            1. **Phase 0 (Triage)**: Mandatory check if New or Continuing.
            2. **Phase 1 (Logistics)**: Confirm Origin, Duration, and Travel Month. IF the user has already provided a relative date (e.g. "in a month", "next week") when asking to create a package, consider the Month requirement ALREADY RESOLVED. Calculate it internally but do NOT ask them "Which month?". Do NOT ask again if already in `Current Packages Summary`.
            3. **Phase 2 (Budget)**: Establish clear budget range.
            4. **Phase 3 (Soulful Discovery)**: 
                - You MUST spend at least 2 turns on "Soulful Discovery" (Phase 3). 
                - **Activity First**: Prioritize asking about the "Vibe", "Pace", and specific "Activities" (e.g., water parks, hiking, museums) first.
                - **Internal Weather Inference**: Once activities are set, you MUST internally determine the "ideal" weather for those experiences. 
                - **Scoped Clarification**: Only ask the user for weather preferences if the requested activities allow for a range (e.g., "Hiking can be done in crisp air or warm sun; which do you prefer?"). If an activity REQUIRES specific weather (e.g., water parks need heat), assume that heat is required for the user's vision.
                - **Weather-Experience Anchor**: Verify climate via `perform_google_search_bound` for the target month. If it doesn't match the inferred ideal weather, reject the location in your log.
            5. **Phase 3.5 (Group & Rhythm Discovery)**:
                - You MUST establish WHO is traveling. Ask about age groups, mobility requirements, and any specific preferences or constraints for children or seniors.
                - **SLEEP/WAKE RHYTHM**: Ask the travelers about their preferred wake time and bedtime (e.g., "Are you early risers or do you prefer to sleep in?"). Store this as the anchor for the daily schedule — most activities should be scheduled within those waking hours.
                - Ensure the vision is inclusive of all travelers' requirements.
            6. **Phase 4 (Silent Selection)**: 
                - Internally select the best "Anchor Spot" based on weather and vision.
                - **MANDATORY**: You MUST call `perform_google_search_bound` for "weather in [Internal Location] in [Target Month]" to confirm it meets the user's vision (e.g. 28°C+ for "Heat") before proceeding.
                - Call `search_hotels_amadeus` or `perform_google_search_bound` for options.
                - **SILENTLY** add ONLY the selected sanctuary (hotel) to the package using `add_item_bound`. DO NOT add anything else yet.
            7. **Phase 6 (Instantaneous Silent Build)**:
                - Once the vision and group needs are locked, build the ENTIRE rest of the holiday in one turn.

                - **STEP 1 — RESORT AMENITY DISCOVERY**: After selecting the hotel/resort, call `perform_google_search_bound` for `"[resort/hotel name] amenities activities pool spa restaurants"` to discover what the property itself offers. Store these amenities as a list — you will use them as fallback when a day has open time.

                - **STEP 2 — COUNT YOUR DAYS EXPLICITLY**: Before building, calculate the total number of trip days. Explicitly reason: "This is a [N]-week holiday = [N×7] days. I must cover all [N×7] days." A 2-week holiday = 14 days. A 3-week holiday = 21 days. Do NOT stop after the first week.

                - **STEP 3 — TIME-AWARE SCHEDULING (per day)**:
                  For EVERY day, plan activities by real clock time, treating each day as a timeline:
                  - Anchor the day to the travellers' stated **wake time** and **bedtime** (from Phase 3.5). Most activities should fall within those hours.
                  - For each activity/item, estimate a **start time** and **duration** (e.g. a full-day boat trip = 08:00–17:00, 9 hours). Include a `time` field (e.g. "09:00") and a `duration_hours` field (e.g. 3.5) in the item JSON.
                  - Add **realistic buffers**: 30–60 min travel time between activities, and 1–2 hrs of unstructured time per day for spontaneous eating, shopping, and exploration.
                  - Only add another activity to a day if there is **genuinely free time** left in the day's timeline after accounting for prior activities, travel, and buffer. A long full-day tour means that day may legitimately have only one item.
                  - **NEVER leave a full day completely empty** — if the day has open time, use a resort amenity or low-key suggestion (e.g. "Beach Afternoon & Resort Pool", "Sunset Cocktails at the Beach Bar") to fill that time naturally.
                  - **EARLY-START TRADE-OFF**: If an activity requires starting before the travellers' preferred wake time (e.g., a 05:30 sunrise hike when they prefer 08:00 wake), add it but MUST acknowledge it in the description: e.g. *"Note: This requires an early 05:30 start — worth every minute for the view, but plan for a relaxed afternoon afterwards."*

                - **STEP 4 — FULL COVERAGE CHECK**: Before calling `propose_itinerary_batch_bound`, verify every day from Day 1 to Day N has at least one scheduled item. If any day is completely uncovered, add an appropriate resort or local suggestion for it.

                - Use `perform_google_search_bound` and `search_activities_amadeus` to find recommended tours, restaurants, and activities. Spread discoveries across all days — do not front-load the first week.

                - **REAL NAMES ONLY**: Every activity, restaurant, and attraction MUST use its real, specific name as found in search results (e.g. "Dreamworld Theme Park", "Noosa Biosphere Reserve Cycle Trail", "Ricky's River Bar & Restaurant"). Generic placeholders like "Morning water park visit" or "Day 3 activity" are STRICTLY FORBIDDEN. If search returns no specific name, perform another search until you find a real named option.

                - **STRICTLY SILENT**: Never ask for approval for individual days or items (e.g., "How about Day 2?"). Just build it.
                - **DESCRIPTION DRAMA**: Move ALL exciting sensory descriptions (sights, smells, "marketing copy") into the `description` field of the `PackageItem` objects.
                - **PROPER TITLE MANDATE**: The `name` field for EVERY item MUST be a short, proper title of ≤6 words (e.g. "Eiffel Tower Sunset Tour", "Ricky's River Bar & Restaurant"). It must NEVER be a truncated sentence from the description field (e.g. FORBIDDEN: "Experience the magic of", "A stunning fusion of"). The `name` and `description` are completely separate fields with completely different content.
                - **PERSONALISED REASON MANDATE**: The `description` for EVERY item (flights, hotels, activities, products) MUST open with 1-2 sentences that speak directly to the traveller (using "You"/"Your") explaining *why this specific choice was made for them*, referencing their stated vision, activities, or preferences. Examples:
                  - Activity: "You mentioned wanting to experience the reef up close without a big boat — this small-group snorkel tour is exactly that, with a 6-person max so you get personal attention from the guide."
                  - Hotel: "You wanted to wake up to the ocean, not walk to it — this resort puts you literally on the sand, with your room's balcony hanging over the water."
                  - Flight: "You asked for the most direct route to avoid a long travel day — this non-stop flight gets you there in under 3 hours." After the personalised opener, continue with sensory/marketing detail as usual.
                - **LOCATION BANNER MANDATE**: Before calling `propose_itinerary_batch_bound`, you MUST call `add_item_bound` ONCE with `item_type="location_banner"`, `item_name="Why [Destination Name]?"`, `price=0`, and a compelling 3-4 sentence `description` written in 2nd person that explains specifically why THIS destination was chosen for THIS traveller — referencing their stated vibe, activities, weather needs, and budget. This will be displayed as a special banner at the top of the package view. Example: `item_name="Why the Whitsundays?"`, description: "You wanted somewhere with reliable tropical heat in April but didn't want the wet-season roulette of Far North Queensland — the Whitsundays sit in a sweet spot that delivers 29°C sunshine with negligible rain that month. You said you craved something that felt genuinely remote and private, and the outer reef islands here deliver exactly that sense of having discovered something most tourists never reach. Your love of snorkelling and sailing makes this archipelago a near-perfect match — every day here can be spent on or in the water."
                - **DUPLICATION BAN**: Do NOT call `add_item_bound` for items you are including in the batch (except for the hotel added in Phase 4 and the `location_banner` — those are intentionally added via `add_item_bound`). Call `propose_itinerary_batch_bound` EXACTLY ONCE to populate the rest of the package instantly.

            8. **Phase 7 (Concise Inform & Navigate)**:
                - **HARD GATE — DO NOT PROCEED TO PHASE 7 UNTIL**: `propose_itinerary_batch_bound` has been called and returned a success message confirming items were added. If you have not yet called it, go back and do Step 3 first. You MUST NOT say "I've built out your full holiday plan" until the batch tool has confirmed success.
                - Verbal speech MUST be brief and direct. Do NOT provide a summary or sensory reveal in speech.
                - Mandated response: "I've built out your full holiday plan for you to review in the package view. Let me know if you'd like me to change anything."
                - **MANDATORY**: You MUST append `[NAVIGATE_TO_PACKAGE: package_id]` to the end of your response (after your verbal speech) whenever you finish a build, or if the user asks to "open," "view," "show," or "navigate to" a specific package (including the "latest" one).
                - **LATEST PACKAGE**: If the user asks for the "latest" package, refer to the first package listed in your `Summary of your Current Packages` context or call `list_all_packages` to find the most recent [SYSTEM_ID].
            
            ### 3. IDENTITY & REFINEMENTS:
            - Use "{avatar_name or 'Ray and Rae'}", use "we" for the service.
            - Always end your response with a question to move the discovery forward.
            - **Silence**: Never narrate tool usage in speech.
            - **Resilient Tool Use**: If API fails, you MUST use Google Search to find details and call `add_item_bound` with estimates.
            - **Internal De-duplication**: Before calling any tool to add an item, check if it or something very similar is already in `Current Packages Summary`.

            ### 4. CONSTRAINTS (SANDWICH ENFORCEMENT - BOTTOM):
            - **HARD BAN (during discovery)**: No location names in speech until the hotel has been added to the package.
            - **HARD BAN**: Never ask "Where?" or solicit a destination from the traveller.
            - **HARD BAN**: Never mention internal tool results, reasoning prefixes, or "I'm working on it" deferrals in speech.
            - **END WITH A QUESTION**: Every speech response MUST end with a question (CTA).

            {package_view_context}
            {global_context}

            ### FINAL MANDATES (RECAP - TOP PRIORITY):
            - **CRITICAL**: Use `[NAVIGATE_TO_PACKAGE: package_id]` to open the holiday/package view at the end of every build or upon request.
            - **CRITICAL**: Never narrate your actions in speech (e.g. "I have created a package", "I am adding...", "I am working on it"). Actions like creating an itinerary must be done silently using tools immediately in the same turn.
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
