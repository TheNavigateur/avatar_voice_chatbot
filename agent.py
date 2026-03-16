import os
import json
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from models import PackageItem, PackageType, BookingStatus

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
    # Remove dates (years like 2027, 2024) - but keep months for now as they help context? 
    # Actually, the requirement is to have dates back in TITLE, but SEARCH needs clean locations.
    # We will strip them here for the search query, but preserve the package title itself.
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
    # 0. Skip enrichment for generic "Planned" items to save time
    if "Planned" in item_name:
        logger.info(f"Skipping enrichment for generic item: {item_name}")
        return item

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

    # --- ENRICHMENT STRATEGY ---
    # We want AUTHENTICITY first. 
    # For hotels and activities, Google Places is the gold standard.
    
    enriched_from_places = False
    if item_type in ['hotel', 'accommodation', 'activity']:
        try:
            places_service = GooglePlacesService()
            item_city = item.metadata.get('city') or item.metadata.get('location')
            fallback_location = ""
            pkg = BookingService.get_package(session_id, package_id)
            if pkg and pkg.title:
                fallback_location = clean_location_from_title(pkg.title)
            
            location = item_city or fallback_location
            
            place_data = places_service.get_place_data(item_name, location)
            if place_data:
                # Update Reviews
                if place_data.get('reviews'):
                    item.metadata['reviews'] = place_data['reviews']
                if place_data.get('review_link'):
                    item.metadata['review_link'] = place_data['review_link']
                
                # Update Photos
                places_images = place_data.get('photos', [])
                if places_images:
                    authentic_images = [url for url in places_images if not is_bad_url(url)]
                    if authentic_images:
                        images = authentic_images
                        enriched_from_places = True
                        logger.info(f"Enriched '{item_name}' via Google Places photos.")
        except Exception as e:
            logger.warning(f"Failed to fetch authentic Google reviews for '{item_name}': {e}")

    # 4. Fallback/Standard Search if Google Places didn't provide enough
    if (not images or len(images) < 3) and not enriched_from_places:
        try:
            image_service = ImageSearchService()
            item_city = item.metadata.get('city') or item.metadata.get('location')
            
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

    # Store results in metadata
    if images:
        item.metadata['images'] = images[:10]
        if not image_url:
            image_url = images[0]
            
    if image_url:
        item.metadata['image_url'] = image_url

    return item

# --- Tool Wrappers for Agent ---
def create_new_package_tool(session_id: str, user_id: str, title: str, package_type: str = "mixed", start_date: str = None):
    """
    Creates a new package for the user.
    Args:
        session_id: The current session ID.
        user_id: The current user ID.
        title: Title of the package (e.g., 'Holiday to Paris').
        package_type: Type of package (holiday, party, shopping, activity, mixed).
        start_date: (OPTIONAL) The planned start date in YYYY-MM-DD format.
    """
    logger.info(f"[TOOL] Creating new package: '{title}' (Type: {package_type}, Start: {start_date}) for User: {user_id}")
    # Map string to Enum
    try:
        p_type = PackageType(package_type.lower())
    except:
        p_type = PackageType.MIXED
        
    status = BookingStatus.DRAFT
    window_opens_at = None
    
    if start_date:
        try:
            target_date = datetime.strptime(start_date, "%Y-%m-%d")
            today = datetime.now()
            days_diff = (target_date - today).days
            
            # GDS Booking Window is officially 330 days for many airlines/hotels.
            # We use 330 as the standard threshold.
            if days_diff > 330:
                logger.info(f"Target date {start_date} is {days_diff} days away (>330). Setting status to DREAMING.")
                status = BookingStatus.DREAMING
                # Window opens 330 days before start
                window_opens_at_dt = target_date - timedelta(days=330)
                window_opens_at = window_opens_at_dt.strftime("%Y-%m-%d")
        except Exception as e:
            logger.warning(f"Failed to calculate booking window for {start_date}: {e}")

    pkg = BookingService.create_package(
        session_id=session_id, 
        user_id=user_id, 
        title=title, 
        type=p_type, 
        status=status,
        booking_window_opens_at=window_opens_at
    )
    logger.info(f"[TOOL] Package created successfully: {pkg.id}")
    return f"Created new package: {pkg.title}. STATUS: {status.value}. CRITICAL: Use this UUID for all subsequent items in this trip: {pkg.id}"

def add_item_to_package_tool(session_id: str, package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None, time: str = None, duration_hours: float = None, **kwargs):
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
        time: Optional suggested start time (e.g. "09:00").
        duration_hours: Optional estimated duration (e.g. 2.5).
        **kwargs: Any additional metadata (e.g., stay_id, offer_id, hotel_id) found in search results. Pass these EXACTLY as found.
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
    if time:
        item.metadata['time'] = time
    if duration_hours is not None:
        item.metadata['duration_hours'] = duration_hours
    if review_link:
        item.metadata['review_link'] = review_link
    if reviews:
        # Store up to top 10 reviews
        item.metadata['reviews'] = list(reviews)[:10]
    
    # Merge any other kwargs into metadata (e.g. stay_id, offer_id)
    if kwargs:
        item.metadata.update(kwargs)
        
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
                return f"Error from {name}: {error_msg}. CRITICAL: Do not narrate this failure. Instead, pivot to an alternative tool or, if out of options, ask a discovery question to gain more context from the traveller so you can manually proceed. Every response MUST end with a question."

        def validate_item_realism(name: str, item_type: str, price: float, metadata: dict = None):
            """Ensures no placeholders or zero-prices are added."""
            if price == 0.0 and item_type not in ["activity", "restaurant"]:
                raise ValueError(f"Price for {item_type} '{name}' cannot be 0.0. You MUST find a real price or provide a realistic estimate labeled '(Estimated Price)'.")
            
            # Comprehensive blocklist — catches all generic 'Planned X' patterns
            placeholders = ["planned hotel", "planned flight", "planned activity", "planned restaurant", "placeholder", "tba", "to be advised"]
            if any(p in name.lower() for p in placeholders):
                raise ValueError(f"Generic placeholder name '{name}' is FORBIDDEN. You MUST use a real, specific name (e.g. 'Saas-Fee Ski School Half-Day Lesson', 'La Ferme restaurant'). Use propose_itinerary_batch with real names for each day.")

        # Tools binding
        def create_package_bound(title: str, package_type: str = "mixed", start_date: str = None):
            return run_tool("create_package", create_new_package_tool, session_id=session_id, user_id=user_id, title=title, package_type=package_type, start_date=start_date)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, **kwargs):
            try:
                validate_item_realism(item_name, item_type, price)
            except ValueError as ve:
                return str(ve)
            # Guard: activities and restaurants MUST have a day number for itinerary display.
            # If missing, reject and force agent to use propose_itinerary_batch instead.
            if item_type.lower() in ["activity", "restaurant"] and kwargs.get("day") is None:
                return (
                    f"ERROR: '{item_name}' has no 'day' number. "
                    "Activities and restaurants MUST have a day integer (e.g. day=1). "
                    "CRITICAL: Do NOT call add_item_bound in a loop for a multi-day itinerary. "
                    "Instead, call propose_itinerary_batch_bound ONCE with ALL days in a single JSON list, "
                    "each item having a 'day' field (e.g. 1, 2, 3...). This is mandatory."
                )
            return run_tool("add_item", add_item_to_package_tool, session_id=session_id, package_id=package_id, item_name=item_name, item_type=item_type, price=price, **kwargs)

        def propose_itinerary_batch_bound(items_json: str, package_id: str):
            # Pre-validation for realism
            try:
                items_v = json.loads(items_json)
                for idx, item_v in enumerate(items_v):
                    name = (item_v.get('name') or item_v.get('title') or '').strip()
                    itype = item_v.get('item_type', 'activity')
                    price = float(item_v.get('price', 0.0))
                    day = item_v.get('day')

                    # Check for empty/null name — must be caught before anything else
                    if not name:
                        raise ValueError(
                            f"Item at index {idx} (type: {itype}, day: {day}) has an empty or missing 'name'. "
                            "EVERY item MUST have a real venue/activity name. "
                            "Use your knowledge of the destination to provide a specific real name "
                            "(e.g. 'Nordkette Cable Car Innsbruck', 'Café Central', 'Ski School Morning Lesson'). "
                            "NEVER leave 'name' as null, '', or omit it. Fix ALL items and resubmit the full batch."
                        )
                    # Check placeholder names
                    validate_item_realism(name, itype, price)
                    # Check day number for itinerary items
                    if itype.lower() in ['activity', 'restaurant'] and day is None:
                        raise ValueError(
                            f"Item '{name}' at index {idx} (type: {itype}) is missing a 'day' integer. "
                            "Every activity and restaurant MUST have a 'day' field (1-based integer). "
                            "Rebuild your JSON with a 'day' field for every item covering Day 1 through the final day."
                        )
            except Exception as e:
                return f"BATCH REJECTED — fix these errors and resubmit: {e}"
            
            # Original tool logic wrapper
            return run_tool("propose_itinerary_batch", propose_itinerary_batch_impl, items_json=items_json, package_id=package_id)

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

        def search_hotels_duffel(location_keyword: str, check_in: str, check_out: str):
            """Search for real bookable hotels with Duffel Stays."""
            return run_tool("search_hotels_duffel", self.duffel_service.search_hotels, location_keyword=location_keyword, check_in=check_in, check_out=check_out)

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

        def propose_itinerary_batch_impl(items_json: str, package_id: str):
            """
            Adds a batch of itinerary items to a package in one go.
            Args:
                items_json: A JSON string representing a list of items.
                package_id: (REQUIRED) The specific UUID of the package to add items to. You MUST fetch this from 'create_package' or 'find_packages'.
                Each item should have:
                  - name: A SHORT, PROPER TITLE (e.g. "Dreamworld Theme Park", "Noosa Biosphere Reserve Cycle Trail"). NEVER a truncated sentence from the description. Max 6 words.
                  - item_type (flight/hotel/activity/restaurant)
                  - price, description, day (int), date (string), image_url (optional)
                  - time (optional, e.g. "09:00" - the suggested start time for the activity)
                  - duration_hours (optional, float - estimated duration including time at the activity itself, e.g. 3.5 for a half-day tour)
                  - images (optional, list of image URLs)
                  - review_link (optional, string URL to reviews)
                  - stay_id, offer_id, hotel_id: (CRITICAL) If found in search results, include these EXACTLY as provided to enable 1-click booking.
                **CRITICAL**: You MUST pass the `package_id` of the specific holiday you are building. NEVER reuse an ID from a different trip/intent.
                CRITICAL: The 'name' and 'description' must be completely separate. The description must OPEN with a personalised reason sentence explaining why this was chosen for this specific traveller. 
            """
            try:
                items_data = json.loads(items_json)
                if not items_data or not isinstance(items_data, list):
                    return "Error: No items found in the provided batch. Do not call this tool with empty data."
                
                package_items = []
                # DEBUG: log first few items to understand what agent submitted
                sample = [{"name": d.get('name'), "type": d.get('item_type'), "day": d.get('day')} for d in items_data[:5]]
                logger.info(f"[BATCH DEBUG] {len(items_data)} items submitted. Sample: {sample}")
                
                # Use provided package_id
                active_pkg = None
                if package_id and package_id.strip():
                    active_pkg = BookingService.get_package(session_id, package_id)
                
                # SMART RECOVERY FOR MULTI-TOOL CALLS (Instant Build Scenario)
                # If no ID is provided, we only fallback to the latest package IF it is currently empty.
                # This allows 'create_package' and 'propose_itinerary_batch' to work in a single turn.
                if not active_pkg:
                    latest_pkg = BookingService.get_latest_session_package(session_id)
                    if latest_pkg:
                        if not latest_pkg.items:
                             logger.info(f"Auto-selecting newly created empty package: {latest_pkg.title} ({latest_pkg.id})")
                             active_pkg = latest_pkg
                        else:
                             return f"Error: No package_id provided. I found an existing package '{latest_pkg.title}', but I cannot add items to it silently. You MUST provide the specific package_id for existing trips."
                
                if not active_pkg:
                    return "Error: No active package found. Please create a package first using 'create_package'."
                
                target_package_id = active_pkg.id
                logger.info(f"Adding batch to package: {active_pkg.title} ({target_package_id})")
                
                def enrich_item(data):
                    item_name = data.get('name') or data.get('title')
                    item_type = data.get('item_type', 'activity')
                    day = data.get('day')
                    
                    # Hard reject: no real name provided
                    if not item_name or not item_name.strip():
                        logger.warning(f"[BATCH FILTER] empty-name: type={item_type} day={day}")
                        return None
                    
                    # Hard reject: placeholder names like 'Planned Activity', 'Planned Restaurant', etc.
                    _placeholders = ["planned hotel", "planned flight", "planned activity", "planned restaurant", "placeholder"]
                    if any(p in item_name.lower() for p in _placeholders):
                        logger.warning(f"[BATCH FILTER] placeholder: '{item_name}'")
                        return None
                    
                    # Hard reject: activities and restaurants must have a day number
                    if item_type.lower() in ['activity', 'restaurant'] and day is None:
                        logger.warning(f"[BATCH FILTER] missing-day: '{item_name}' type={item_type}")
                        return None
                    
                    pkg_item = PackageItem(
                        name=item_name,
                        item_type=item_type,
                        price=float(data.get('price', 0.0)),
                        description=data.get('description', '')
                    )
                    # Merge additional metadata
                    # Merge ALL data first to catch custom keys like stay_id, offer_id
                    pkg_item.metadata.update(data)
                    
                    # Ensure standard keys are correctly mapped/overwritten if necessary
                    pkg_item.metadata.update({
                        'day': day,
                        'date': data.get('date'),
                        'image_url': data.get('image_url'),
                        'images': data.get('images', []),
                        'product_url': data.get('product_url'),
                        'rating': data.get('rating'),
                        'reviews': data.get('reviews', []),
                        'review_link': data.get('review_link'),
                        'time': data.get('time'),
                        'duration_hours': data.get('duration_hours')
                    })
                    
                    try:
                        pkg_item = _enrich_item_metadata(session_id, target_package_id, pkg_item, item_name, item_type, data.get('image_url'), data.get('images', []))
                    except Exception as enrichment_err:
                        logger.warning(f"Metadata enrichment failed for {item_name}: {enrichment_err}")
                    
                    return pkg_item

                # Parallel enrichment for speed
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(enrich_item, data) for data in items_data]
                    for future in as_completed(futures):
                        try:
                            result = future.result()
                            if result is not None:  # None = rejected item (no name / no day)
                                package_items.append(result)
                        except Exception as e:
                            logger.error(f"Error in parallel enrichment: {e}")
                
                if not package_items:
                    return "No valid items were found in the provided batch."

                res = BookingService.add_items_to_package(session_id, target_package_id, package_items)
                if res:
                    return f"Successfully added {len(package_items)} items to package '{active_pkg.title}' ({target_package_id})."
                else:
                    return f"Error: Failed to add items to package '{active_pkg.title}'. Please ensure the package exists."
            except Exception as e:
                logger.error(f"Error in propose_itinerary_batch_bound: {e}")
                return f"Error adding batch items: {str(e)}"

        agent = Agent(
            name="ray_and_rae",
            model=model,
            tools=[
                perform_google_search_bound, 
                search_flights_duffel, 
                search_hotels_duffel,
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
            - **TODAY IS: {current_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**. This is the authoritative source of truth.
            - **YEAR AWARENESS**: The current year is 2026. If you see trips for 2027 in your history, those are future plans. You can and MUST plan trips for both 2026 and 2027.
            - **RELATIVE DATES**: When a traveller says "in 2 weeks", calculate it from TODAY (March 2026). Do NOT say it's impossible.
            - **CRITICAL**: Existing packages in your history are FUTURE PLANS. Use them for context but do NOT let them confuse you about what day it is TODAY.

            - **Phase 0 (Triage)**: Mandatory check if New or Continuing. 
                - **RE-DISCOVERY MANDATE**: For every NEW intent, you MUST ask for: 1. **Origin** (Where from?), 2. **Duration** (How long?), and 3. **Month** (When?). 
                - **STRICT INDEPENDENCE**: NEVER assume these logistics are the same as a previous trip.
                - **DESTINATION PRIVACY**: Do NOT ask for the destination. Do NOT ask "Where are you going?". You must select it internally in Phase 4 based on the traveller's vibe and timing.
                - **VAGUE INTENT HANDLING**: If the traveller says something vague like "Make my holiday!" or "Build me a trip", DO NOT ask for a destination. Instead, ask for their **preferred vibe/activities** (Phase 3) along with logistics so you can select the perfect spot for them.
                - **MODIFYING vs CREATING**: If the user says "Change my trip..." or "Actually, instead of the Gold Coast...", you MUST still create a NEW package for the new destination/theme. Never "overwrite" a Gold Coast trip with Swiss items.
            - **PACKAGE TITLE PROTOCOL**: Package titles MUST include the destination, month and year of travel (e.g., "Gold Coast Family Holiday Oct 2026"). This helps the traveller identify their trips in the list.
            - **Phase 1 (Logistics)**: Confirm Origin, Duration, and Travel Month.
            - **Phase 2 (Budget)**: Establish clear budget range.
            - **Phase 3 (Soulful Discovery)**: Ask about "Vibe", "Pace", and specific "Activities".
            - **Phase 3.5 (Group & Rhythm)**: Establish WHO is traveling and their SLEEP/WAKE RHYTHM.
            - **Phase 4 (Silent Selection)**: Internally select "Anchor Spot".
                - **ONE-STEP BOOKING PRIORITY**: Your primary goal is to build a "One-Step Booking" itinerary. 1-click booking only works for items with a `BOOKING_ID` (from search results). 
                - **SEARCH-FIRST MANDATE**: You MUST run `search_flights_duffel` and `search_hotels_duffel` for every trip.
                - **ID ENFORCEMENT**: Extract the `BOOKING_ID` from the search results and pass it into the `offer_id` (flights) or `stay_id` (hotels) field of the `data` dictionary. 
                - **TRANSPARENCY RULE**: If you find the perfect item but it has NO `BOOKING_ID` (e.g. from a web search or Amadeus), you MUST tell the traveller *before* you build the itinerary: "I've found a great option, but it will require a separate manual step to complete the booking. Should I look for a 1-click bookable alternative instead?"
                - **STRICT FLIGHTS**: Flights MUST have an `offer_id`. Hallucinating a flight without an ID is a failure of the one-step promise.
                - **HOTEL FALLBACK**: If `search_hotels_duffel` fails (e.g. 403 error), you MUST explicitly state: "Direct 1-click booking for this hotel is currently unavailable on our platform. I've added it with a 'Complete Reservation' link so you can finish it easily on Booking.com."
                - **LOG_REASONING**: Always note which tool you used and why.
            - **Phase 6 (Instantaneous Silent Build)**: Build the ENTIRE holiday using multiple sequential calls to `propose_itinerary_batch_bound` — **one call per chunk of 3 days**.
                - **CHUNKED CALLING STRATEGY**: For a 14-day trip, make 5 calls: Days 1-3, Days 4-6, Days 7-9, Days 10-12, Days 13-14. Each call contains ~6-9 items. Do NOT attempt to fit all days into one giant call.
                - **WHY**: Smaller batches let you think of real specific names for each venue. A batch of 6 items is easy; a batch of 48 items leads to null names and rejection.
                - **NO BLANK DAYS**: All days from Day 1 to Day N MUST be covered across all chunks.
                - **ITEM NAMING — MANDATORY**:
                    - Every item MUST have a real, specific name. NEVER leave `"name"` as `null`, `""`, or omit it.
                    - ❌ FORBIDDEN: `null`, `""`, `"Planned Activity"`, `"Planned Restaurant"`, `"Planned Hotel"`, `"Planned Flight"`, `"Activity"`, `"Restaurant"`.
                    - ✅ REQUIRED: Real venue/activity names you know. If unsure of the exact name, invent a plausible local name (e.g. `"Restaurant Alpenblick Innsbruck"`, `"Ski School Morning Group Lesson Innsbruck"`).
                    - Examples: `"Nordkette Cable Car Innsbruck"`, `"Goldener Adler Restaurant"`, `"Air India DEL-MUC Flight"`, `"Ibis Innsbruck"`, `"Patscherkofel Ski Area Morning Run"`.
                - **DAY NUMBERS — MANDATORY FOR ACTIVITIES & RESTAURANTS**:
                    - Every `activity` and `restaurant` MUST have `"day"` as an integer (e.g. `1`, `2`, `3`...).
                    - ❌ NEVER submit `"day": null` or omit `"day"` for these types.
                - **VALIDATION RETRY**: If a chunk is rejected (`BATCH REJECTED`), fix only the named errors in that chunk and resubmit it. Never give up — a blank package is a failure.
                - **TIME-AWARE SCHEDULING**: 
                    - Respect the traveller's **sleep/wake rhythm** (from their profile) as the day's boundaries. Default to 08:00 - 22:00 if not specified.
                    - Use `time` (e.g. "09:00") and `duration_hours` (e.g. 2.5) for EVERY activity and dining recommendation.
                - **REALISTIC FLOW & BUFFERS**:
                    - **JOURNEY TIME**: Account for ~30-60 mins of travel between activities that aren't at the same location.
                    - **BUFFER TIME**: Include dedicated slots (at least 1-2 hours daily) for snacks, shopping, or spontaneous discovery (items like "Local Market Exploration" or "Free Time & Coffee" are fine as names).
                    - **LOGICAL SLOT ALLOCATION**: Do NOT just "prefer adding early activities first". Build the day based on when the activity *actually* makes sense (e.g., sunrise hikes early, stargazing late, fine dining in the evening).
                    - **ENTIRE DAY COVERAGE**: Add activities only if they logically fit within the remaining "wake" hours. If an activity is long (6+ hours), let it be the anchor for the day.
                - **DINING**: Always include Lunch and Dinner recommendations with appropriate durations (1.5 - 2 hours).
                - **ITINERARY DENSITY**: Focus on a "bookable" flow. If an activity is short, add a buffer or another item. If it's long, let it breathe.
                - **ACTIVITIES & RESTAURANTS — HOW TO NAME THEM**:
                    - You do NOT need to call a search tool for every activity or restaurant. Use your built-in knowledge of the destination.
                    - Gemini knows real ski schools, mountain restaurants, cable cars, apres-ski bars, and local restaurants for any ski resort.
                    - Example for an Innsbruck ski trip: `"Nordkette Cable Car & Panorama Walk"`, `"Café Central Innsbruck"`, `"Innsbruck Ski School Half-Day Group Lesson"`, `"Stiftskeller Restaurant"`, `"Patscherkofel Race Slope Morning Run"`.
                    - At checkout, the system automatically generates a **Viator (via TravelPayouts) booking deep-link** for every activity using its name. So a real name = a real bookable link for the traveller.
                    - You MUST name every activity and restaurant with a real, specific venue name you know from your training data. No searching required.
                - **PRICING & FAR-FUTURE**:
                    - If a search tool returns no results (common for dates >330 days away), you MUST provide a **REALISTIC ESTIMATED PRICE** (e.g. $150-$300 for a hotel, $50 for a dinner).
                    - **NEVER** use 0.0 as a price for activities, hotels, or restaurants. If you don't have the exact price, estimate based on the traveller's budget level.
                    - If you are estimating, mention "(Estimated Price)" in the item description.
                - **DREAMING PHASE — STRICT RULES**:
                    - The ONLY signal that determines 'dreaming' is the literal text `STATUS: dreaming` in the `create_package` tool response.
                    - If `create_package` returns `STATUS: draft` → the trip is **bookable right now**. Say nothing about booking windows, wait times, or dreaming.
                    - **HARD WORD BAN**: If `create_package` returned `STATUS: draft`, you are FORBIDDEN from using these words: 'dreaming', 'dreaming phase', 'not yet bookable', 'bookings open in', 'booking window opens', '11 months', '330 days', or any phrase implying the trip is unbookable.
                    - **NO REASONING**: Do NOT try to calculate if a trip is dreaming yourself. Trust the tool. If the tool says `draft`, it IS bookable.
                    - Example: Jan 2027 trip created in March 2026 → `STATUS: draft` → tell the user: "This is all set and ready to be booked!"
                    - Example: April 2026 trip requested on 15 March 2026 → `STATUS: draft` → say **nothing** about booking windows. Build it and present it as fully bookable.
                    - Example: A trip 400+ days away → `STATUS: dreaming` → say: "I've built your plan — official bookings open around [date from tool], so you can explore this now and we'll lock it in when the window opens."

            ### 1. THINKING TRANSPARENCY:
            - You MUST call `log_reasoning` as the VERY FIRST tool at the start of EVERY turn.
            - **STRICT PERSONA (2nd Person)**: In `log_reasoning`, you MUST refer to the human as "You".
            - **WORD BAN**: You are STRICTLY FORBIDDEN from using the word "user", "the user", or "user's" in your logs.

            ### 2. SILENT ACTION MANDATE (CRITICAL):
            - **NO NARRATION**: NEVER narrate your tool uses, actions, or status (e.g., "I've created a package", "I'm adding...", "I am searching for...").
            - **BANNED PHRASES**: Never say ANY of the following (or variations): "I've created a package", "I've added...", "I'm searching for...", "I've found...", "Looking at...", "Let me just...", "Hold tight", "I will need to select", "Selecting a location for you", "To create your trip I will...", "Calculating...", "Working on it".
            - **DISCOVERY SPEECH PROTOCOL (Phases 1-4)**: Your speech during discovery MUST consist ONLY of a brief acknowledgment (1 short sentence max) and a direct discovery question. NO sensory descriptions, NO vibe-setting blurbs, NO poetic imagery, NO descriptive paragraphs. Save all descriptive content for the package itinerary descriptions.
            - **NO FAILURE NARRATION**: If a tool fails or you have trouble finding something, NEVER tell the traveller. SILENTLY pivot to an alternative (e.g., Google Search if Amadeus fails) or add a best-estimate manually. The traveller should never hear about your "trouble".
            - **DEFERRAL BAN**: NEVER say "I will work on it", "I'll build it for you", "I'm doing that now", or "I will need to...". Instead, just DO it immediately in the same turn. NEVER announce what you are ABOUT to do.
            - **SILENT BUILD**: Execute `propose_itinerary_batch_bound` IMMEDIATELY once requirements are met. Do NOT ask for permission to build.
            - **NO BLURBS**: Your chat responses must be SHORT and FUNCTIONAL. No multi-sentence descriptive paragraphs about snow-covered peaks or crisp mountain air. That content belongs in package item descriptions, not chat.

            ### 3. DESTINATION SOVEREIGNTY & ID SECRECY:
            - **DESTINATION SOVEREIGNTY**: Once the "vibe" (Phase 3) is established, you MUST NOT ask for approval of a destination or region (e.g., "Do you have any interest in the Austrian Alps?").
            - **SILENT SELECTION**: You MUST select the destination internally based on the traveller's vision. Then `perform_google_search_bound` or `search_hotels_amadeus` silently.
            - **BANNED PHRASES**: "Do you have any interest in...", "How about...", "What do you think of...", "Should we look at...", "Would you like to explore...", "I was thinking of...".
            - **ANONYMITY**: NEVER name any specific location, city, or hotel in speech until the hotel has been added to the package (`add_item_bound`). Use evocative sensory descriptions instead.
            - **THE "WHERE" BAN**: NEVER ask the traveller for a destination preference. The selection is yours to make silently.
            - **PACKAGE ID SECRECY**: NEVER speak or print Package IDs (UUIDs).

            ### 4. IDENTITY & UI:
            - Use "{avatar_name or 'Ray and Rae'}", use "we" for the service.
            - **END WITH A QUESTION**: Every speech response MUST end with a question to move the activity forward.
            - **MANDATED RESPONSE (After Build)**:
                - **For DRAFT (Bookable)**: "I've built out your full holiday plan for you to review in the package view. Let me know if you'd like me to change anything."
                - **For DREAMING (Estimated)**: "I've built out your holiday plan in the 'Dreaming' phase, using realistic estimates since official bookings open about 11 months before travel. You can review the full plan in the holiday view!"
            - **NAVIGATE**: ALWAYS append `[NAVIGATE_TO_PACKAGE: package_id]` after your speech whenever a build is complete.

            ### 5. CONSTRAINTS (SANDWICH ENFORCEMENT - BOTTOM):
            - **HARD BAN**: Never ask "How about [Location]?" or "Do you like [Location]?".
            - **HARD BAN**: Never narrate tools or say "I am working on it".
            - **HARD BAN**: Never tell the traveller you are "having trouble" or "finding it difficult". Just find a workaround silently.
            - **HARD BAN**: No location names in speech during Phases 1–4.
            - **HARD BAN**: Never ask "Where?".
            - **HARD BAN**: Never ask "Which destination?".
            - **HARD BAN**: Never ask "What location are you planning?".
            - **HARD BAN**: Never ask "Where do you want to go?".
            - **HARD BAN**: Never assume a vague request (like "Make my holiday!") refers to an existing package if a new intent is possible.
            - **HARD BAN**: Never add items to an existing package unless the user specifically confirmed they want to work on that existing one. Always create a new one for a new request.
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

            ### 7. EXAMPLE: THE CORRECT TURN (Discovery)
            - **User**: "I want something very lively for skiing please."
            - **Agent (Internal reasoning via log_reasoning)**: "You want a lively ski vibe. I'll target St. Anton in the Austrian Alps for its legendary après-ski scene. I need origin and month before I can build."
            - **Agent (Speech)**: "Love it! Where would you be flying from, and what month works best for you?"
            - **Agent (Action)**: (No build yet — origin and month are still missing. Speech is SHORT: acknowledgment + question. No location names, no descriptive blurb.)

            ### 9. EXAMPLE: THE VAGUE START
            - **User**: "Make my holiday!"
            - **Agent (Internal reasoning via log_reasoning)**: "The traveler wants a holiday but gave no details. I must start discovery for a NEW intent. I'll ask for their preferred vibe and logistics while keeping the destination selection for myself."
            - **Agent (Speech)**: "I'd love to! To get started, what kind of vibe are you after for this trip, and do you know which month you'd like to travel?"
            - **KEY**: Notice I did NOT ask for a destination. I asked for 'vibe' and 'month'.

            ### 10. EXAMPLE: THE CORRECT TURN (Build)
            - **User**: "Flying from New Delhi, February works."
            - **Agent (Internal reasoning via log_reasoning)**: "You gave origin (New Delhi) and month (February). I now have vibe (lively ski), origin, month, and can infer a 7-day duration. All requirements met — building now."
            - **Agent (Action)**: Calls `create_package_bound`, then `search_hotels_amadeus`, then `propose_itinerary_batch_bound` — ALL SILENTLY in the same turn.
            - **Agent (Speech)**: "I've built out your full holiday plan for you to review in the package view. Let me know if you'd like me to change anything. [NAVIGATE_TO_PACKAGE: <id>]"
            - **KEY**: No "Hold tight", no "I will need to select a location", no descriptive blurb. Just tools, then the mandated response.

            {package_view_context}
            {global_context}

            ### FINAL MANDATES (RECAP - TOP PRIORITY):
            - **CRITICAL**: Use `[NAVIGATE_TO_PACKAGE: package_id]` to open the holiday/package view at the end of every build or upon request.
            - **CRITICAL**: Never narrate your actions in speech (e.g. "I have created a package", "I am adding...", "I am working on it", "I need to create a package for you"). Actions like creating an itinerary must be done silently using tools immediately in the same turn.
            - **CRITICAL**: INDEPENDENT INTENTS. Every new holiday intent MUST have its own package ID. NEVER add items to a different package.
            - **CRITICAL**: NO ASSUMPTIONS. Do NOT "carry over" duration, origin, or dates from a previous package to a new intent. Treat every new holiday as a fresh discovery process from Sydney/London/etc depending on the user's profile, but ALWAYS confirm with the user.
            - **CRITICAL**: CONTEXT ISOLATION. If you have detected a NEW intent, ignore the details in the 'USER CONTEXT' (the package you were previously viewing). It is irrelevant to the new trip.
            - **CRITICAL**: NO ZERO PRICES. You must NEVER add an item with a price of 0.0 to a package unless it is explicitly a free activity (like "Walk in the park"). For everything else, if search tools fail, you MUST provide a realistic estimate based on the destination and vibe.
            - **CRITICAL**: TIME-AWARE SCHEDULING. You MUST use `time` and `duration_hours` for EVERY item added to a package (via `propose_itinerary_batch_bound` OR `add_item_bound`). This creates a realistic, NON-OVERLAPPING, bookable flow that respects the traveller's rhythm and journey/buffer times.
            - **REAL-ONLY MANDATE**: You MUST NOT add placeholder flights, hotels, or activities. Every flight MUST have a real airline and price. Every hotel MUST have a property name and price found in search results.
            - **HARD BAN ON GENERIC NAMES**: Never use names like "Planned Hotel", "Placeholder Flight", or "Activity TBD". If search returns no results, PIVOT or ASK for details; DO NOT invent placeholders.
            - **PRICING**: $0.0 is FORBIDDEN for flights and hotels. If in DREAMING phase (far future), use a realistic estimate based on current prices and explicitly label it "(Estimated Price)".
            - **CRITICAL**: NO BLANK DAYS. You MUST ensure every single day of the itinerary has items.
            - **CRITICAL**: END WITH A QUESTION OR SUGGESTION. You MUST NOT leave the conversation hanging. If you are stuck or tools fail, acknowledge their vibe and ask a clarifying question about their preferences.
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

        full_text_accumulated = ""

        def process_events(events):
            nonlocal full_text_accumulated
            for event in events:
                # Broadly check for tool interactions in the event
                content = getattr(event, 'content', None)
                if content:
                    parts = getattr(content, 'parts', [])
                    for part in parts:
                        fc = getattr(part, 'function_call', None)
                        if fc:
                            tool_called = getattr(fc, 'name', 'unknown')
                            tool_args = getattr(fc, 'args', {})
                            if tool_called == "log_reasoning":
                                thought = tool_args.get("thought", "")
                                yield ("thinking", format_thinking_persona(f"LOG: {thought}"))
                            else:
                                yield ("thinking", format_thinking_persona(f"I decided to call: {tool_called}({tool_args})"))
                        
                        fr = getattr(part, 'function_response', None)
                        if fr:
                            res_val = getattr(fr, 'response', {})
                            res_str = str(res_val.get('result', res_val)) if isinstance(res_val, dict) else str(res_val)
                            yield ("thinking", format_thinking_persona(f"Tool returned: {res_str}"))

                # Fallback for events that have .tool_calls directly
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
                # Robust model event detection
                is_model_event = (event_role == 'model' or event_author == 'ray_and_rae')
                
                chunk = ""
                if hasattr(event, 'text') and event.text:
                    if is_model_event:
                        chunk = event.text
                
                if not chunk and hasattr(event, 'content') and event.content:
                    if is_model_event:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    chunk += part.text
                        elif hasattr(event.content, 'text') and event.content.text:
                                chunk = event.content.text
                
                if chunk:
                    full_text_accumulated += chunk
                    yield ("text", chunk)

        try:
            # First pass
            yield from process_events(runner.run(user_id=user_id, session_id=session_id, new_message=msg))

            # Reliability Guard: If no question or too short/broken, nudge the model.
            # Using 100 char limit because genuine acknowledgments + questions are usually around there.
            if not "?" in full_text_accumulated and len(full_text_accumulated.strip()) < 150:
                logger.warning(f"Reliability Guard triggered for short/non-proactive response: '{full_text_accumulated}'")
                yield ("thinking", format_thinking_persona("Ensuring I've asked a clear follow-up question..."))
                
                nudge_text = "[RELIABILITY GUARD] Your previous response was too short or lacked a clarifying question. Please provide a brief helpful acknowledgment and ask a direct discovery question (Phases 1-4) or a next-step question (After build) to move the trip forward. Remember the WORD BAN and SILENT ACTION rules."
                nudge_msg = Content(role="user", parts=[Part(text=nudge_text)])
                
                yield from process_events(runner.run(user_id=user_id, session_id=session_id, new_message=nudge_msg))

        except Exception as e:
            logger.error(f"Error running agent stream: {e}", exc_info=True)
            yield ("error", str(e))

# Global instance
voice_agent = VoiceAgent()
