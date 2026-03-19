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

def is_discovery_complete(profile_content: str, current_message: str = "", session_history: str = "") -> bool:
    """ Checks if the 6 mandatory requirements are present specifically for the current intent. """
    msg_only = (current_message or "").lower()
    hist_only = (session_history or "").lower()
    
    # 1. Detect if a NEW intent was started in this session
    # We look for word-based triggers to avoid fragile substring matches (e.g. "new holiday" vs "new ski holiday")
    vague_starts = [
        "make my holiday", "make a holiday", "build me a trip", "plan a trip", 
        "start a trip", "let's plan something", 
        "start a new one", "brand new holiday", "something else"
    ]
    
    # More robust check for "new holiday" or "new trip" including variations like "new ski holiday"
    is_reset_requested = any(v in msg_only for v in vague_starts) or \
                         (("new" in msg_only) and ("holiday" in msg_only or "trip" in msg_only or "plan" in msg_only))
                         
    if is_reset_requested:
        logger.info(f"[PHASE_CHECK] New intent detected in current message. Forcing Discovery.")
        return False

    # Find the last time the history contains a 'vague start' or a reset invitation from Ray
    last_vague_idx = -1
    all_vague_markers = vague_starts + ["new holiday", "new trip", "new plan"]
    for v in all_vague_markers:
        idx = hist_only.rfind(v)
        if idx > last_vague_idx:
            last_vague_idx = idx
            
    # 2. Define the 'Search Space' for requirements
    # If a new intent started recently, we ONLY look for requirements AFTER that point.
    if last_vague_idx != -1:
        # Intent started in this session. Only trust what was said SINCE then.
        search_space = (hist_only[last_vague_idx:] + "\nUser: " + msg_only).lower()
        logger.info("[PHASE_CHECK] New intent detected in history. Using fresh context only.")
    else:
        # No vague start in recent history. Fallback to profile (likely continuing a specific trip).
        search_space = ((profile_content or "") + "\n" + hist_only + "\nUser: " + msg_only).lower()
        logger.info("[PHASE_CHECK] No recent reset. Using profile + history.")
    
    # CRITICAL: We only want to satisfy requirements based on what the USER said.
    # We filter the search space to only lines starting with "User: " or "Profile: " (implied)
    # However, since profile_content doesn't have prefixes, we'll just split and filter the session history parts.
    
    lines = search_space.split('\n')
    user_context = ""
    for line in lines:
        if line.startswith("agent:") or line.startswith("model:"):
            continue # Skip agent's own questions
        user_context += line + "\n"
    
    combined = user_context.lower()
    
    # Requirement 1: Origin
    origin_ok = any(x in combined for x in ["origin", "departing", "flying from", "from:"]) or \
                (any(city in combined for city in ["london", "paris", "new york", "berlin", "tokyo", "manchester"])) # Common origins fallback
    
    # Requirement 2: Duration
    duration_ok = any(x in combined for x in ["duration", "how long", "weeks", "days", "nights"])
    
    # Requirement 3: Month
    month_ok = any(x in combined for x in ["month", "when", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan ", "feb ", "mar ", "apr ", "jun ", "jul ", "aug ", "sep ", "oct ", "nov ", "dec ", "in 2 months", "in 1 week", "next month", "months from now", "weeks from now"])
    
    # Requirement 4: Budget
    budget_ok = any(x in combined for x in ["budget", "cost", "spend", "$", "£", "€", "price range"])
    
    # Requirement 5: Vibe/Activities
    categories = ["beach", "ski", "city", "mountains", "nature", "culture"]
    actions = ["activities", "interested in", "prefer", "like to", "want to", "visiting", "water park", "bike", "hike", "museum", "dining", "nightlife", "various", "child friendly"]
    
    category_hit = any(c in combined for c in categories)
    action_hit = any(a in combined for a in actions)
    vibe_ok = ("vibe" in combined) or (category_hit and action_hit)
    
    # Requirement 6: Group/Travellers
    group_ok = any(x in combined for x in ["group", "travelling", "travellers", "wife", "husband", "son", "daughter", "kids", "children", "child", "people", "adults", "me and", "family"])

    results = [origin_ok, duration_ok, month_ok, budget_ok, vibe_ok, group_ok]
    is_complete = all(results)
    
    if not is_complete:
        missing = []
        if not origin_ok: missing.append("Origin")
        if not duration_ok: missing.append("Duration")
        if not month_ok: missing.append("Month")
        if not budget_ok: missing.append("Budget")
        if not vibe_ok: missing.append("Vibe")
        if not group_ok: missing.append("Group")
        logger.info(f"[PHASE_CHECK] Discovery incomplete. Missing: {missing}")
        
    return is_complete

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
def create_new_package_tool(session_id: str, user_id: str, title: str, description: str = None, package_type: str = "mixed", start_date: str = None):
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
        description=description,
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
        def create_package_bound(title: str, description: str = None, package_type: str = "mixed", start_date: str = None):
            return run_tool("create_package", create_new_package_tool, session_id=session_id, user_id=user_id, title=title, description=description, package_type=package_type, start_date=start_date)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float = 0.0, **kwargs):
            # Alias support for single item additions
            itype = (item_type or kwargs.get('type') or 'activity').lower()
            name = (item_name or kwargs.get('title') or '').strip()
            
            # Validation
            if not name:
                return "FAILED: Name missing. Correct Format: {'name': 'Specific Venue Name', 'item_type': 'hotel/flight/activity/restaurant', ...}"
            
            try:
                validate_item_realism(name, itype, price)
            except ValueError as ve:
                return str(ve)
            # Guard: activities and restaurants MUST have a day number for itinerary display.
            # If missing, reject and force agent to use propose_itinerary_batch instead.
            if itype in ["activity", "restaurant"] and kwargs.get("day") is None:
                return (
                    f"ERROR: '{name}' has no 'day' number. "
                    "Activities and restaurants MUST have a day integer (e.g. day=1). "
                    "CRITICAL: Do NOT call add_item_bound in a loop for a multi-day itinerary. "
                    "Instead, call propose_itinerary_batch_bound ONCE with ALL days in a single JSON list, "
                    "each item having a 'day' field (e.g. 1, 2, 3...). This is mandatory."
                )
            return run_tool("add_item", add_item_to_package_tool, session_id=session_id, package_id=package_id, item_name=name, item_type=itype, price=price, **kwargs)

        def propose_itinerary_batch_bound(items_json: str, package_id: str):
            # Pre-validation and Schema Auto-Fix
            try:
                items_v = json.loads(items_json)
                fixed_items = []
                for idx, item_v in enumerate(items_v):
                    # Alias support: title -> name, type -> item_type
                    name = (item_v.get('name') or item_v.get('title') or '').strip()
                    itype = (item_v.get('item_type') or item_v.get('type') or 'activity').lower()
                    price = float(item_v.get('price', 0.0))
                    day = item_v.get('day')

                    # Check for empty/null name
                    if not name:
                        raise ValueError(
                            f"Item at index {idx} has an empty 'name'. "
                            "Correct JSON Item Template: {'name': 'Specific Venue Name', 'day': 1, 'item_type': 'activity', 'price': 50.0, 'description': '...'}"
                        )
                    
                    # Check for day in itinerary items
                    if itype in ['activity', 'restaurant'] and day is None:
                        raise ValueError(
                            f"Item '{name}' is missing a 'day' integer. "
                            "Every activity/restaurant MUST have a 'day' field (e.g. 1, 2, 3). "
                            "Correct JSON Item Template: {'name': '...', 'day': 1, 'item_type': 'activity', ...}"
                        )

                    validate_item_realism(name, itype, price)
                    
                    # Update item with fixed aliases for the implementation call
                    item_v['name'] = name
                    item_v['item_type'] = itype
                    fixed_items.append(item_v)
                
                # Re-serialize fixed items
                items_json = json.dumps(fixed_items)
                
            except Exception as e:
                return f"BATCH REJECTED — fix these errors and resubmit: {e}"
            
            # Original tool logic wrapper
            result = run_tool("propose_itinerary_batch", propose_itinerary_batch_impl, items_json=items_json, package_id=package_id)
            
            # Check for success and add a chunking reminder if it's a batch add
            if isinstance(result, str) and "successfully added" in result.lower():
                result += "\n\n[RELIABILITY REMINDER]: You MUST continue adding chunks sequentially (e.g., if you just did Days 1-3, you MUST now call this tool for Days 4-6) until YOU REACH THE LAST DAY of the traveller's requested duration. ONLY provide your text response once EVERY day of the trip has a full schedule."
            
            return result

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

        # 1. Determine Phase and Load Prompt
        session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
        session_history = ""
        if session and session.events:
            for event in session.events:
                role = getattr(event, 'role', 'unknown').lower()
                text = ""
                if hasattr(event, 'text') and event.text:
                    text = event.text
                elif hasattr(event, 'content') and hasattr(event.content, 'parts'):
                    texts = [p.text for p in event.content.parts if hasattr(p, 'text')]
                    text = "\n".join(texts)
                
                if text:
                    session_history += f"{role}: {text}\n"
        
        profile_content = ProfileService.get_profile(user_id)
        discovery_complete = is_discovery_complete(profile_content, message, session_history)
        
        prompt_file = "prompts/builder_prompt.md" if discovery_complete else "prompts/discovery_prompt.md"
        with open(prompt_file, "r") as f:
            instruction_template = f.read()
            
        instruction = instruction_template.replace(
            "{current_time}", current_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ).replace(
            "{avatar_name}", avatar_name or 'Ray and Rae'
        ).replace(
            "{package_view_context}", package_view_context
        ).replace(
            "{global_context}", global_context
        )

        # 2. Define Toolsets (Guarding)
        COMMON_TOOLS = [
            log_reasoning,
            save_user_info_bound,
            list_all_packages,
            find_packages,
            get_package_details_bound
        ]
        
        DISCOVERY_TOOLS = COMMON_TOOLS + [
            perform_google_search_bound,
            search_products_bound,
            check_amazon_stock_bound,
            search_amazon_bound,
            search_amazon_with_reviews_bound
        ]

        BUILDER_TOOLS = COMMON_TOOLS + [
            perform_google_search_bound, 
            search_flights_duffel, 
            search_hotels_duffel,
            search_hotels_amadeus,
            search_activities_amadeus,
            create_package_bound, 
            add_item_bound,
            remove_item_bound,
            delete_package_bound,
            propose_itinerary_batch_bound
        ]

        active_tools = BUILDER_TOOLS if discovery_complete else DISCOVERY_TOOLS
        logger.info(f"[PHASE_GUARD] Discovery Complete: {discovery_complete}. Using {prompt_file} with {len(active_tools)} tools.")

        agent = Agent(
            name="ray_and_rae",
            model=model,
            tools=active_tools,
            instruction=instruction
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
                                pass # NEVER share internal reasoning logs with the human.
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
                            pass # NEVER share internal reasoning logs with the human.
                        else:
                            yield ("thinking", format_thinking_persona(f"I decided to call: {tool_called}({tool_args})"))

                tool_outputs = getattr(event, 'tool_outputs', None)
                if tool_outputs:
                    for to in tool_outputs:
                        tool_name = getattr(to, 'name', 'unknown')
                        if tool_name == "log_reasoning":
                            pass # NEVER share reasoning outcomes with the human.
                        else:
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
                    # CRITICAL: Filter out internal system markers, reliability guard nudges, or instructions
                    if chunk.strip().startswith("[") or "RELIABILITY GUARD" in chunk:
                         logger.info(f"[STREAM FILTER] Suppressed internal marker/nudge: {chunk.strip()[:50]}...")
                         continue
                    
                    # NEW: Build Stream Filter
                    # If discovery is complete, ONLY allow mandated response or specific commands
                    # This prevents the model from narrating its "helpfulness" mid-build.
                    allowed_keywords = ["I've built out your full holiday plan", "I've built out your holiday plan in the 'Dreaming' phase", "[NAVIGATE_TO_PACKAGE:"]
                    if discovery_complete:
                         is_allowed = any(k in chunk for k in allowed_keywords)
                         # We allow chunks that are part of a larger mandated response (sometimes models stream in small bits)
                         # But if the accumulated text starts drifting into narration, we block it.
                         potential_full_text = full_text_accumulated + chunk
                         if not any(k in potential_full_text for k in allowed_keywords) and len(potential_full_text) > 50:
                              logger.info(f"[BUILD FILTER] Suppressed narrative filler: {chunk.strip()[:50]}...")
                              continue

                    full_text_accumulated += chunk
                    yield ("text", chunk)

        try:
            # First pass
            yield from process_events(runner.run(user_id=user_id, session_id=session_id, new_message=msg))

            # Reliability Guard: If no question or too short/broken, nudge the model.
            # Using 100 char limit because genuine acknowledgments + questions are usually around there.
            if not "?" in full_text_accumulated and len(full_text_accumulated.strip()) < 150:
                logger.warning(f"Reliability Guard triggered for short/non-proactive response: '{full_text_accumulated}'")
                if discovery_complete:
                    nudge_text = "[RELIABILITY GUARD] You have completed the build but did not provide the MANDATED RESPONSE. You MUST respond with: 'I've built out your full holiday plan for you to review in the package view. Let me know if you'd like me to change anything. [NAVIGATE_TO_PACKAGE: package_id]'"
                else:
                    nudge_text = "[RELIABILITY GUARD] Your previous response was too short or lacked a clarifying question. Please provide a brief helpful acknowledgment and ask a direct discovery question (Phases 1-4) to move the trip forward. Remember the WORD BAN and SILENT ACTION rules."
                
                nudge_msg = Content(role="user", parts=[Part(text=nudge_text)])
                yield from process_events(runner.run(user_id=user_id, session_id=session_id, new_message=nudge_msg))

        except Exception as e:
            logger.error(f"Error running agent stream: {e}", exc_info=True)
            yield ("error", str(e))

# Global instance
voice_agent = VoiceAgent()
