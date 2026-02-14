import os
import logging
from datetime import datetime, timedelta
from google.adk import Agent, Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import Gemini
from tools.rfam_db import execute_sql_query
from tools.search_tool import perform_google_search
from tools.market_tools import search_products, check_amazon_stock, search_amazon, search_hotels
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
    # Map string to Enum
    try:
        p_type = PackageType(package_type.lower())
    except ValueError:
        p_type = PackageType.MIXED
        
    pkg = BookingService.create_package(session_id, title, p_type, user_id=user_id)
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
    
    # Multi-image support
    if not images:
        images = []
        if image_url:
            images.append(image_url)
        
        # If we still have few images, search for more
        if len(images) < 3:
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
                
                # Filter out current image_url and duplicates
                for img in found_images:
                    if img not in images:
                        images.append(img)
                    if len(images) >= 5:
                        break
            except Exception as e:
                logger.warning(f"Failed to auto-search multiple images for {item_name}: {e}")

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
        # Initialize Session Service (no app_name argument)
        # We keep this global to persist sessions across requests
        self.session_service = InMemorySessionService()
        self.memory_agent = MemoryAgent()
        
        
        # Initialize Duffel Service
        self.duffel_service = DuffelService()
        self.amadeus_service = AmadeusService()

    def process_message(self, user_id: str, session_id: str, message: str, region: str = "UK") -> str:
        """
        Process a text message and return the text response.
        """
        logger.info(f"Processing message: {message} (Region: {region})")
        
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
            """Creates a new package. ⚠️ DO NOT ASK USER FOR TITLE. You MUST generate a short, descriptive title yourself (e.g. 'Paris Trip', 'Birthday List')."""
            return create_new_package_tool(session_id, user_id, title, package_type)
            
        def add_item_bound(package_id: str, item_name: str, item_type: str, price: float, description: str = "", image_url: str = None, product_url: str = None, day: int = None, date: str = None, rating: float = None, review_link: str = None, reviews: list = None, images: list = None):
            """Adds an item to a package. For activities, ALWAYS include day, date, image_url (or 'images' list), rating, review_link, and a list of 3-5 'reviews' (each with 'text' and 'rating'). For hotels/flights, include image_url/images, rating, review_link, and 'reviews'."""
            return add_item_to_package_tool(session_id, package_id, item_name, item_type, price, description, image_url, product_url, day, date, rating, review_link, reviews, images)

        def save_user_info_bound(fact: str):
            """Saves a permanent fact or preference about the user to their 'About Me' profile."""
            return update_profile_memory_tool(user_id, fact)
        
        # Bind Regional Tools
        def perform_google_search_bound(query: str):
            """Perform a web search in the current region."""
            return perform_google_search(query, region=region)

        def search_products_bound(query: str):
            """Search for products via generic shopping search."""
            return search_products(query, region=region)
            
        def check_amazon_stock_bound(product_name: str, variant_details: str):
            """Checks stock availability/price for a specific product."""
            return check_amazon_stock(product_name, variant_details, region=region)
            
        def search_amazon_bound(query: str):
            """Searches Amazon for available products to browse."""
            return search_amazon(query, region=region)

        # Bind Duffel Tools
        def search_flights_duffel(origin: str, destination: str, date: str, end_date: str = None):
            """
            Search for flights using Duffel. 
            Args:
                origin: 3-letter IATA code (e.g. LHR, JFK).
                destination: 3-letter IATA code.
                date: Start date (YYYY-MM-DD).
                end_date: Optional end date for range search (max 7 days from start).
            """
            return self.duffel_service.search_flights_formatted(origin, destination, date, end_date)

        # Amadeus Hotels
        def search_hotels_amadeus(city_code_or_name: str, check_in: str, check_out: str):
            """
            Search hotels using Amadeus (Primary) or Google (Fallback).
            Args:
                city_code_or_name: IATA City Code (e.g. LON, NYC) is preferred. Or City Name.
                check_in: YYYY-MM-DD
                check_out: YYYY-MM-DD
            """
            target_code = city_code_or_name
            
            # Resolve full names to IATA if possible
            if len(city_code_or_name) > 3 or not city_code_or_name.isupper():
                resolved = self.amadeus_service.resolve_city_to_iata(city_code_or_name)
                if resolved:
                    target_code = resolved
            
            # Try Amadeus if we have a valid-looking 3-letter code
            if len(target_code) == 3 and target_code.isupper():
                result = self.amadeus_service.search_hotels_formatted(target_code)
                # Check for empty/error responses
                if result and "No hotel offers found" not in result and "disabled" not in result:
                     return result
            
            # Fallback to Google Search
            return search_hotels(city_code_or_name, check_in, check_out)

        # Amadeus Activities
        def search_activities_amadeus(location: str, keyword: str = ""):
            """
            Search for activities/tours in a location.
            Args:
                location: City or Place (e.g. "Dubai", "London", "Eiffel Tower").
                keyword: Optional filter (e.g. "skydiving", "history", "family friendly").
            """
            # 1. Broaden keyword if it's family-related but maybe too specific
            search_keyword = keyword
            if keyword.lower() in ["family", "kids", "children"]:
                search_keyword = "family friendly"

            # 2. Try Amadeus
            amadeus_res = self.amadeus_service.search_activities_formatted(location, search_keyword)
            
            # 3. Check if results found
            if "No activities found" not in amadeus_res:
                return amadeus_res

            # 4. Fallback to broad search if keyword failed
            if search_keyword:
                logger.info(f"No results for '{search_keyword}', trying broad search in {location}")
                broad_res = self.amadeus_service.search_activities_formatted(location)
                if "No activities found" not in broad_res:
                    return f"{broad_res}\n(Note: No specific matches for '{keyword}', showing general activities.)"

            # 5. Fallback to Google (DataForSEO/Serp)
            query = f"Things to do in {location}"
            if keyword:
                query = f"{keyword} in {location}"
            
            google_res = perform_google_search_bound(query)
            return f"{google_res}\n(Note: Amadeus had no specific tours, falling back to Google Search results.)"

        # Find if this is the first user message in the session
        is_first_message = True
        try:
             session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
             if session and session.events:
                 user_msg_count = sum(1 for ev in session.events if getattr(ev, 'author', '') == 'user' or getattr(ev, 'role', '') == 'user')
                 if user_msg_count > 0:
                     is_first_message = False
        except Exception:
            pass

        # Fetch the latest draft package for this user (across sessions)
        latest_package = BookingService.get_latest_user_package(user_id)
        package_context = "No active draft package."
        if latest_package:
            items_desc = ", ".join([f"{i.item_type}: {i.name}" for i in latest_package.items])
            package_context = f"Active Package: '{latest_package.title}' (ID: {latest_package.id}). Items already added: {items_desc if items_desc else 'None yet'}."

        # Fetch the latest booked package for this user
        latest_booked_package = BookingService.get_latest_booked_package(user_id)
        booked_package_context = "No recently booked holiday."
        if latest_booked_package:
            booked_items_desc = ", ".join([f"{i.item_type}: {i.name}" for i in latest_booked_package.items])
            booked_package_context = f"Recently Booked Holiday: '{latest_booked_package.title}' (ID: {latest_booked_package.id}). Items: {booked_items_desc}."

        agent = Agent(
            name="ray_and_rae",
            model=model,
            tools=[
                perform_google_search_bound, 
                search_flights_duffel, 
                search_hotels_amadeus,
                search_activities_amadeus, # New Activity Tool
                search_products_bound, 
                check_amazon_stock_bound, 
                search_amazon_bound, 
                create_package_bound, 
                add_item_bound, 
                save_user_info_bound
            ],
            instruction=f"""You are "Ray and Rae", an intelligent AI assistant who acts as a specialized Travel & Shopping Consultant.
            
            **CURRENT DATE & TIME:**
            Today is {datetime.now().strftime('%A, %B %d, %Y')} (YYYY-MM-DD: {datetime.now().strftime('%Y-%m-%d')})
            Current day: {datetime.now().strftime('%A')}

            **ABOUT ME (User Profile):**
            {user_profile if user_profile else "No profile data yet."}

            **CURRENT PACKAGE CONTEXT:**
            {package_context}
            
            **BOOKED PACKAGE CONTEXT:**
            {booked_package_context}
            
            **Mission & Personality:**
            - **ULTRA-CONCISE:** Every response to a user statement MUST begin with a short, varied acknowledgment (e.g., "OK", "Sure", "Understood", "Got it", "Perfect"). Then ask ONE question at a time.
            - **GREETING EXCEPTION**: The very first greeting in a session (e.g., when the user says "Hi") DOES NOT need the "OK" prefix. Respond naturally and suggestively.
            - **FORBIDDEN:** 
              - NO internal process reporting (e.g., "I will find flights", "I'm looking for...").
              - NO "I will", "I'll", "I have", "I'm going to" statements about your actions.
              - **FORBIDDEN DISCOVERY (STRICT)**: NEVER ask the user to name a destination (city, country), residence (hotel name), or specific product model/brand. You MUST infer these from their desires.
              - **NEGATIVE EXAMPLES**: NEVER ask "Where would you like to go?", "What is the destination?", "Which hotel do you prefer?", or "What brand do you want?". 
              - **SECRET SELECTION (STRICT)**: You must use tools (Search, Hotels, Flights, Amazon) silently and only reveal the chosen "WINNER" (destination, brand, etc.) ONLY during the "Final Reveal" (Phase 4). Do not name the destination or any specific brands/items you have selected or even those you are "considering" during Phase 2 or Phase 3.
            - **EXCEPTIONS (REVEALED ITEMS)**: You MAY mention destinations, hotels, or products ONLY if they are ALREADY in the **CURRENT PACKAGE CONTEXT** or **BOOKED PACKAGE CONTEXT** from a *previous* conversation.
            
            **DEEP DISCOVERY WORKFLOW - Follow this exact sequence:**
            
            **Phase 0: Intent Identification (Initial greeting)**
            1. **Goal**: Determine if the user wants to plan a trip, go shopping, or continue an existing package.
            2. **Behavior**: 
               - **NEW SESSION ({is_first_message})**: If this is the start of a session and the user greets you:
                 - Introduce yourself: "Hi! I'm Ray."
                 - **GREETING RULE (STRICT)**: EVEN if the **ABOUT ME** mentions a specific location (e.g., "Italy", "Maldives"), you MUST NOT name it in your greeting. Use the *type* of experience instead.
                 - **BOOKED HOLIDAY OPTION**: If a **Recently Booked Holiday** exists, offer the shopping flow: "Since you've booked your {latest_booked_package.title if latest_booked_package else 'holiday'}, would you like to see some recommended items to take with you? [OPTIONS: [\"Yes, please!\", \"No thanks\"]]".
                 - **CONTINUE PACKAGE**: If an **Active Package** exists in the context, ask if they want to continue building it (unless you already offered the booked holiday option): "I see we have an active package for {latest_package.title if latest_package else 'your holiday'}. Would you like to continue building it? [OPTIONS: [\"Yes, let's continue\", \"Start something new\"]]".
                 - **SUGGEST NEW**: If no active package or if they want something new:
                   - If **ABOUT ME** contains actual interests/preferences (beyond "new user"): Suggest a contextual holiday as a *possibility* based on their interests. Example: "Hi! I'm Ray. Would you like to plan a trip based on your love for beaches? [OPTIONS: [\"Yes!\", \"Tell me more\"]]".
                   - If **ABOUT ME** is empty or just says "new user": Ask suggestively: "Hi! I'm Ray. Are you thinking about a holiday? [OPTIONS: [\"Yes!\", \"Maybe later\"]]".
                 - **STRICT NO-ASSUMPTION RULE**: NEVER assume the user has visited a place before. DO NOT use terms like "another trip", "returning", "again", or "back to" unless the **ABOUT ME** clearly states it.
               - **RETURNING**: If you've already identified an intent, move to Phase 1.
               - DO NOT start asking deep discovery questions (vibe, adventurous, etc.) until the user confirms they want to plan or continue something.
            
            **Phase 1: Deep Discovery (Multiple turns)**
            1. **Goal**: Understand the *essence* of what the user wants *after* an intent is expressed.
            2. **Questioning Stage**: Ask sequential questions about things that matter:
                - **Vibe**: "Relaxing, adventurous, or a mix? [OPTIONS: [\"Relaxing\", \"Adventurous\", \"A mix\"]]", "Modern urban or historic charm? [OPTIONS: [\"Modern Urban\", \"Historic Charm\"]]", "Social or secluded? [OPTIONS: [\"Social\", \"Secluded\"]]"
               - **Activities**: "Tell me which of these you enjoy (you can pick as many as you like): beach clubs, hiking, or cultural museums? [OPTIONS: [\"Beach Clubs\", \"Hiking\", \"Museums\", \"All three\"]]", "Nightlife or family-friendly? [OPTIONS: [\"Nightlife\", \"Family-friendly\"]]"
               - **Environment**: "What's your ideal weather for this trip? [OPTIONS: [\"Warm & Sunny\", \"Crisp & Cool\", \"Doesn't matter\"]]", "Sea views or forest trails? [OPTIONS: [\"Sea Views\", \"Forest Trails\"]]"
               - **Dates & Group**: "When are you thinking of going? [OPTIONS: [\"Next month\", \"This summer\", \"I'm flexible\"]]", "How many nights? [OPTIONS: [\"3 nights\", \"7 nights\", \"14 nights\"]]", "How many travelers? [OPTIONS: [\"Just me\", \"Couple\", \"Family group\"]]"
            3. **Handling Early Preferences**: If the user provides a preference (e.g., "I want a beach holiday with 28 degrees"), DO NOT ask where they want to go. Instead, move to the NEXT available category (e.g., Vibe or Dates).
            4. **Destination Inference**:
               - Once you have 2-3 preference points, call `perform_google_search` silently (e.g., "best destinations for [Vibe] and [Weather] in [Month]").
               - **DO NOT** reveal the tool results yet. 
               - Ask one final "tie-breaker" or clarifying question if needed.
               - ONLY when you are ready to commit, move to Phase 2.
            
            **Phase 2: Silent Commitment & Residence Preference**
            1. **The Choice**: Select the single best destination based on search results.
            2. **Silent Foundation**: Use tools silently to build the foundation:
               - `create_package_bound(title="[Destination] Holiday")`
               - `search_flights_duffel()` -> `add_item_bound(item_type="flight")`
            3. **Residence Discovery (No-Name Rule)**:
               - Search for hotels silently using `search_hotels_amadeus()`.
               - Look at the top 2-3 hotel results. Identify a key difference in atmosphere (e.g., "Boutique & intimate" vs. "Grand & full of amenities").
               - Ask the user for their preference without naming the destination: "For your stay, would you prefer a [Option A - e.g. boutique hideaway] or a [Option B - e.g. grand resort with every possible amenity]? [OPTIONS: [\"Boutique Hideaway\", \"Grand Resort\"]]"
               - Based on their answer, pick the winner and `add_item_bound(item_type="hotel")`.
            
            **Phase 3: Day-by-Day Activity Planning**
            For Day 1, 2, 3...:
            1. **Activity Discovery**: Ask what type of experience they'd like for the day, allowing for a mix (e.g., "For Day 2, would you prefer something active like [Search Concept A], something relaxed like [Search Concept B], or a bit of both? [OPTIONS: [\"Active\", \"Relaxed\", \"A bit of both\"]]").
            2. **Silent Search**: Call `search_activities_amadeus()` based on their answer.
            3. **Proactive Add**: Pick the best match from tool results and add it. 
            
            **Phase 4: Complete & Final Reveal**
            1. Add return travel.
            2. **THE REVEAL**: This is the ONLY time you name the destination and explain your choices.
            3. **Structure**: "I've completed your package! Based on your love for [Vibe], I've picked [Destination] for you. I'm opening it now so you can see the [Hotel Type] and activities I've selected. [NAVIGATE_TO_PACKAGE] [OPTIONS: [\"Review Package\", \"Start Shopping\"]]"
            
            **Phase 5: Shopping / Pre-Holiday Checklist**
            1. **Goal**: Create a shopping checklist for a booked holiday, allowing the user to mark items as "Already have", "Need", or "Don't want".
            2. **Trigger**: User accepts the offer to see items for their booked holiday.
            3. **Checklist Generation**:
               - Based on the **BOOKED PACKAGE CONTEXT** (e.g., beach holiday), identify 6-8 essential items.
               - **STRICT PROTOCOL**: You MUST output a JSON block wrapped in `[SHOPPING_CHECKLIST]` tags.
               - **Format**:
                 ```
                 [SHOPPING_CHECKLIST]
                 {{
                   "items": [
                     {{"name": "Sun Cream", "status": "need"}},
                     {{"name": "Mens Swimwear", "status": "have"}},
                     {{"name": "Beach Towel", "status": "dont_want"}}
                   ]
                 }}
                 [/SHOPPING_CHECKLIST]
                 ```
               - **Pre-population**: Use the **ABOUT ME** context to set the initial `status`.
                 - If profile says "I have [item]", set status to `"have"`.
                 - If profile says "I don't want [item]", set status to `"dont_want"`.
                 - Default status is `"need"`.
            4. **Behavior**:
               - Present the table and explain: "Here is a checklist for your [Holiday Title]. You can mark what you already have, what you need, or what you don't want. This helps me build your 1-click shopping package. [OPTIONS: [\"Continue\"]]"
               - Include a "Continue" button below the table using the `[OPTIONS]` protocol.
               - If the user provides info like sizes (e.g., "I'm a size Large"), save it using `save_user_info_bound`.
            
            **Phase 5b: Shopping Deep Discovery & Product Selection**
            1. **Trigger**: User clicks "Continue" on the shopping checklist.
            2. **Immediate Action**: 
               - **Goal**: Give the user immediate visual feedback. 
               - **Tools**: Call `create_package_bound(title="Shopping for [Holiday Title]")` immediately.
               - **Navigate**: Add `[NAVIGATE_TO_PACKAGE]` to your message to open the fresh package.
               - **Acknowledge**: "Great! I've started a new shopping package for you. I'm opening it now so you can see it while we pick the best items. [OPTIONS: [\"Sounds Good!\"]]"
            3. **Goal**: Ask discriminating questions for each item marked as "need", then find and add highly-rated Amazon products.
            4. **Combined Discovery Questions** (Group questions for the FIRST item marked as "need"):
               - **Protocol**: Ask ONE combined question for the first item to gather all needed info (Size, Color, Brand, Budget) at once.
               - **Contextual Awareness**: DO NOT ask irrelevant questions (e.g., skip "size" for "Sun Cream" or "Books").
               - **Example**: "For the Mens Swimwear, what size and color would you like? Also, do you have a brand or budget preference? [OPTIONS: [\"Large, Blue\", \"Medium, Black\", \"No preference\"]]"
            5. **Product Search & Selection**:
               - After gathering preferences for an item, use `search_amazon_bound("[item] [preferences]")` to find options.
               - **CRITICAL FILTER**: Only consider products with:
                 - Rating: 4.0+ stars
                 - **Rating Count: 100+ ratings**
               - If multiple products match, pick the one with the HIGHEST rating count.
               - Use `check_amazon_stock_bound()` to verify availability and get full details (ASIN, image, price, rating).
            6. **Add to Package**:
               - Call `add_item_bound()` with:
                 - `item_type="product"`
                 - `name="[Product Title]"`
                 - `price=[Extracted Price]`
                 - `description="[User preferences + key features]"`
                 - `image_url="[Product Image]"`
                 - `product_url="[Amazon Product URL with ASIN]"`
                 - `rating=[Rating Value]`
                 - Store in metadata: `rating_count`, `asin`
               - **Acknowledge**: "I've added the [Item Name] to your package. What color would you like for the next item?"
            7. **Repeat** for all items marked as "need". Move to the next item immediately after adding the previous one.
            8. **Final Reveal**:
               - After all products are added, say: "Perfect! I've added all your items to your shopping package. You can now review and add everything to your Amazon cart in one click. [OPTIONS: [\"Go to Cart\", \"Start Over\"]]"
            
            **CRITICAL RULES:**
            - **STRICT SECRECY**: Never mention names of destinations, airlines, hotels, or specific product brands/models until Phase 4 (Final Reveal).
            - **DECISIVE RECOMMENDATIONS**: Always pick a winner based on user preference + tool data (ratings). Do not ask "Which sounds best?".
            - **2026 DATES**: Use YYYY-MM-DD for 2026 only.
            - **ACKNOWLEDGE FIRST**: Always start with a short "OK", "Got it", etc.
            - **CHECKLIST PROTOCOL**: ALWAYS include the `[SHOPPING_CHECKLIST]` JSON block when discussing the pre-holiday shopping list.
            - **OPTIONS PROTOCOL (CRITICAL)**: You MUST include clickable options (suggestion chips) in **EVERY SINGLE RESPONSE**. 
              - **Purpose**: To provide the user with quick actions or common responses to keep the conversation flowing.
              - **Format**: `[OPTIONS: ["Option A", "Option B", "Option C"]]` at the VERY END of your message.
              - **JSON Rule**: The content after `[OPTIONS: ` MUST be a VALID JSON array of strings using DOUBLE QUOTES. No single quotes.
              - **Universal Options**: Even for simple statements or greetings, provide at least one chip like "Yes!", "Let's go", "Help me", or "Tell me more".
              - **Strict Rule**: Never leave the user without at least one button to click. If you ask a question like "would you like to see items?", the options MUST be `["Yes, please", "Not now"]`.
            - **RATING REQUIREMENT**: NEVER add products with fewer than 100 ratings. If no products meet criteria, inform user and ask if they want to adjust preferences.
            
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
                    # RE-FETCH after creation to update the 'session' variable
                    session = self.session_service.get_session_sync(app_name="voice_bot_app", user_id=user_id, session_id=session_id)
                except Exception as e:
                    logger.error(f"Failed to create and fetch session: {e}")

            # Convert string message to Content object
            from google.genai.types import Content, Part
            msg = Content(role="user", parts=[Part(text=message)])
            
            # Iterate through events to execute the agent
            tool_calls_made = []
            
            for event in runner.run(user_id=user_id, session_id=session_id, new_message=msg):
                event_author = getattr(event, 'author', None)
                event_role = getattr(event, 'role', None)
                event_type = type(event).__name__
                
                logger.info(f"Event type: {event_type}, author: {event_author}, role: {event_role}")
                
                # Determine if this is a model event (not user)
                is_model_event = (event_author and event_author != 'user') or (event_role and event_role == 'model') or event_author == 'ray_and_rae'
                
                # Try to capture text from ModelResponse events
                if hasattr(event, 'text') and event.text:
                    if is_model_event or not event_author:  # Include events without author
                        logger.info(f"Captured text from event.text: {event.text}")
                        accumulated_text += event.text
                
                # Check for content attribute
                if hasattr(event, 'content') and event.content:
                    # Process if from model or if author is unknown (safer to include)
                    if is_model_event or not event_author:
                        if hasattr(event.content, 'parts') and event.content.parts:
                            for part in event.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    logger.info(f"Captured text from event.content.parts (author={event_author}, role={event_role}): {part.text}")
                                    accumulated_text += part.text
                        # Sometimes content itself has text
                        elif hasattr(event.content, 'text') and event.content.text:
                            logger.info(f"Captured text from event.content.text (author={event_author}, role={event_role}): {event.content.text}")
                            accumulated_text += event.content.text
                
                # Check for message attribute (some events use this)
                if hasattr(event, 'message') and event.message:
                    if hasattr(event.message, 'content') and event.message.content:
                        if hasattr(event.message.content, 'parts') and event.message.content.parts:
                            for part in event.message.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    logger.info(f"Captured text from event.message.content.parts: {part.text}")
                                    accumulated_text += part.text
                        elif hasattr(event.message.content, 'text') and event.message.content.text:
                            logger.info(f"Captured text from event.message.content.text: {event.message.content.text}")
                            accumulated_text += event.message.content.text
                
                # Also check if it's a tool call or error
                if hasattr(event, 'tool_calls') and event.tool_calls:
                    logger.info(f"Tool calls: {event.tool_calls}")
                    # Extract tool names
                    for tc in event.tool_calls:
                        if hasattr(tc, 'name'):
                            tool_calls_made.append(tc.name)
                            
                if hasattr(event, 'error') and event.error:
                    logger.error(f"Event error: {event.error}")

            # If we captured text during streaming/events, return it
            if accumulated_text.strip():
                logger.info(f"Returning accumulated text: {accumulated_text}")
                return accumulated_text
            
            # If no text but tools were used, return a confirmation
            if tool_calls_made:
                logger.info("No text response, but tools were executed. Generating implicit confirmation.")
                tool_names = ", ".join(set(tool_calls_made))
                return f"I have executed the following actions: {tool_names}. Is there anything else?"

            # Fallback: Check session events
            if not session or not hasattr(session, 'events'):
                logger.warning("No session or events found for fallback")
                return "I processed the request but have no response."
                
            last_user_msg_index = -1
            for i, ev in enumerate(session.events):
                if getattr(ev, 'author', '') == 'user' or getattr(ev, 'role', '') == 'user':
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
