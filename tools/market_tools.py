import os
import requests
import json
import logging
import base64

logger = logging.getLogger(__name__)

# DataForSEO Credentials
# DataForSEO Credentials
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

AMAZON_REGIONS = {
    "UK": {
        "location_code": 2826, # United Kingdom
        "tld": "co.uk",
        "currency_symbol": "£",
        "name": "United Kingdom"
    },
    "IN": {
        "location_code": 2356, # India
        "tld": "in",
        "currency_symbol": "₹",
        "name": "India"
    },
    "US": {
        "location_code": 2840, # United States
        "tld": "com",
        "currency_symbol": "$",
        "name": "United States"
    },
    "CA": {
        "location_code": 2124, # Canada
        "tld": "ca",
        "currency_symbol": "C$", # or $
        "name": "Canada"
    },
    "AU": {
        "location_code": 2036, # Australia
        "tld": "com.au",
        "currency_symbol": "A$", # or $
        "name": "Australia"
    }
}
DEFAULT_REGION = "UK"

BASE_URL = "https://api.dataforseo.com/v3/serp/google"

def _get_auth_header():
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return None
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def _search_organic_live(query: str, location_code: int = 2840):
    """Generic helper to call Organic Live Advanced"""
    endpoint = f"{BASE_URL}/organic/live/advanced"
    payload = [{
        "keyword": query,
        "location_code": location_code, 
        "language_code": "en",
        "device": "desktop",
        "os": "windows"
    }]
    
    headers = _get_auth_header()
    if not headers:
        return None, "Error: Credentials not set."

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        data = response.json()
        
        if data.get("status_code") != 20000:
            return None, f"DataForSEO Error: {data.get('status_message')}"
            
        tasks = data.get("tasks", [])
        if not tasks: return None, "No task created."
        
        result = tasks[0].get("result", [])
        if not result: return None, "No result found."
        
        return result[0].get("items", []), None
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return None, f"Error: {e}"

def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search for flights via Organic SERP (Standard Google Search).
    """
    query = f"flights from {origin} to {destination} on {date}"
    items, error = _search_organic_live(query)
    
    if error: return error
    if not items: return "No flight results found."

    summary = f"✈️ **Flight Search Results ('{query}'):**\n"
    found_any = False
    
    # scan for google_flights or organic items
    for item in items:
        # Check for Rich Snippet (Knowledge Graph / Flights)
        if item.get("type") == "google_flights":
            # Sometimes parsing this is complex, let's just indicate we found the tool
            summary += "- Found Google Flights tool. Please check official site for exact realtime prices.\n"
            found_any = True
            
        # Check standard organic results (Expedia, Skyscanner, etc)
        if item.get("type") == "organic":
            title = item.get("title", "Unknown")
            desc = item.get("description", "")
            link = item.get("url", "#")
            # Heuristic to find price in description/title
            summary += f"- {title} ({link})\n  *{desc[:100]}...*\n"
            found_any = True
            
    if not found_any:
        return "No clear flight options found in search results."
        
    return summary

def search_hotels(location: str, check_in: str, check_out: str, requirements: str = "") -> str:
    """
    Search for hotels via Organic SERP.
    Args:
        location: City/Area (e.g. "Paris")
        check_in: YYYY-MM-DD
        check_out: YYYY-MM-DD
        requirements: Optional keywords (e.g. "swimming pool", "near eiffel tower")
    """
    req_str = f" with {requirements}" if requirements else ""
    query = f"hotels in {location}{req_str} from {check_in} to {check_out}"
    items, error = _search_organic_live(query)
    
    if error: return error
    if not items: return "No hotel results found."
    
    summary = f"🏨 **Hotel Search Results ('{query}'):**\n"
    
    for item in items:
        # Check for Hotels Pack
        if item.get("type") == "hotels_pack":
            hotel_items = item.get("items", [])
            for hi in hotel_items:
                name = hi.get("title", "Unknown")
                # Try multiple paths for price: displayed_price (best), current, value, raw
                price_obj = hi.get("price")
                if price_obj:
                    price = (price_obj.get("displayed_price") or 
                             price_obj.get("current") or 
                             price_obj.get("value") or 
                             price_obj.get("raw") or 
                             "N/A")
                else:
                    price = "See Link"
                
                # Sometimes looks like "£120" in parsing
                if str(price).isdigit(): price = f"£{price}"
                
                rating = hi.get("rating", {}).get("value", "N/A")
                desc = hi.get("description", "")
                summary += f"- {name} (~{price}) ⭐ {rating}\n  *Details: {desc}*\n"
            return summary # Return early if we found the pack

    # Fallback to organic
    count = 0
    for item in items:
        if item.get("type") == "organic":
            title = item.get("title", "Unknown")
            link = item.get("url", "#")
            summary += f"- {title} ({link})\n"
            count += 1
            if count >= 5: break
            
    return summary

def search_products(query: str, region: str = "UK") -> str:
    """
    Search for products via Organic SERP (Shopping Results).
    """
    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    query_str = f"buy {query}"
    items, error = _search_organic_live(query_str, location_code=config["location_code"])
    
    if error: return error
    if not items: return "No product results found."
    
    summary = f"🛍️ **Shopping Search Results ('{query_str}'):**\n"
    
    # Check for Shopping Pack
    for item in items:
        if item.get("type") == "shopping_results":
            # Does DataForSEO return items nested? or is 'shopping_results' a list of items?
            # Often it's a block.
            # Let's assume it might be a list of items directly in the main 'items' array 
            # OR a single item of type 'shopping_results' containing 'items'.
            pass

    # Alternative: Scan for type='shopping' or 'commercial'
    count = 0
    for item in items:
        is_shop = item.get("type") == "shopping" or item.get("type") == "commercial" or item.get("type") == "organic"
        if not is_shop: continue

        # Prioritize rich shopping items if they exist
        title = item.get("title", "Unknown")
        price_obj = item.get("price")
        price = price_obj.get("value", "") if price_obj else "" 
        link = item.get("url", "#")
        
        # If no explicit price, try to find text
        if not price and config["currency_symbol"] in (item.get("description") or ""):
            # simple extract
            desc = item.get("description", "")
            # (Very basic extraction logic here, agent will have to interpret)
            price = "See Link"
            
        summary += f"- {title} - {price} - [Link]({link})\n"
        count += 1
        if count >= 5: break
        
    return summary

def _fetch_amazon_candidates(query: str, region: str = "UK") -> list:
    """
    Internal helper to fetch Amazon product candidates from DataForSEO.
    Applies strict availability filtering.
    """
    
    # 1. Credentials
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return []

    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    
    # 2. Query construction
    # Use "site:amazon.{tld}" to bias results
    full_query = f"{query} site:amazon.{config['tld']}".strip()
    
    # 3. Endpoint: Google Organic Live
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": full_query,
        "location_code": config["location_code"], 
        "language_code": "en",
        "depth": 50
    }]
    
    try:
        res = requests.post(url, headers=headers, json=payload)
        data = res.json()
        
        if data.get("status_code") != 20000:
             logger.error(f"DataForSEO Error: {data.get('status_message')}")
             return []
             
        tasks = data.get("tasks", [])
        if not tasks: return []
        
        result_items = tasks[0].get("result")
        if not result_items or not result_items[0]: return []
        
        items = result_items[0].get("items")
        if not items: return []
        
        candidates = []
        
        for item in items:
            # Look for structured shopping blocks
            if item.get("type") == "popular_products":
                sub_items = item.get("items")
                if sub_items:
                    for sub_item in sub_items:
                        candidates.append(sub_item)
            elif item.get("type") == "shopping":
                candidates.append(item)
            elif item.get("type") == "organic":
                candidates.append(item)
                
        # Filter and Prioritize
        valid_candidates = []
        
        for cand in candidates:
            # url = (cand.get("product_url") or cand.get("link") or cand.get("url") or "").lower()
            # title = (cand.get("title") or "").lower()
            snippet = (cand.get("description") or cand.get("snippet") or "").lower()
            
            # --- STRICT AVAILABILITY CHECK ---
            # DataForSEO sometimes provides 'availability' or 'stock_status'
            # We also check for negative keywords in snippet
            
            is_unavailable = False
            
            # 1. Check explicit fields if present
            if cand.get("stock_status") == "OutOfStock": is_unavailable = True
            if cand.get("availability") == "OutOfStock": is_unavailable = True
            
            # 2. Check snippet text overrides
            if "currently unavailable" in snippet: is_unavailable = True
            if "out of stock" in snippet: is_unavailable = True
            if "temporarily out of stock" in snippet: is_unavailable = True
            
            # 3. STRICT PRICE CHECK:
            # If there is NO price object and NO price in snippet, it's likely a dead link/out of stock.
            price_obj = cand.get("price")
            has_price_obj = price_obj and (price_obj.get("current") or price_obj.get("value") or price_obj.get("displayed_price"))
            
            import re
            sym = re.escape(config["currency_symbol"])
            has_price_text = re.search(fr'{sym}(\d+\.?\d*)', snippet) is not None
            
            if not has_price_obj and not has_price_text:
                # Logically, if Amazon doesn't show a price on the SERP, it's usually OOS.
                is_unavailable = True
            
            if is_unavailable:
                continue
            
            # If it passes availability, we keep it as a potential candidate
            valid_candidates.append(cand)
            
        return valid_candidates
        
    except Exception as e:
        logger.error(f"Error in _fetch_amazon_candidates: {e}")
        return []

def search_amazon(query: str, region: str = "UK") -> str:
    """
    Searches Amazon for available products matching the query.
    Use this to 'browse' options before selecting one.
    Returns a summary of top 5 available items.
    """
    candidates = _fetch_amazon_candidates(query, region=region)
    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    if not candidates:
        return f"No available Amazon products found for '{query}' in {config['name']}."
        
    # We want to present a diverse list of identifiable Amazon items
    # Filter for Amazon links primarily for the 'browsing' view
    amazon_candidates = []
    seen_titles = set()
    
    for cand in candidates:
        url = (cand.get("product_url") or cand.get("link") or cand.get("url") or "").lower()
        title = cand.get("title", "Unknown")
        
        if title in seen_titles: continue
        
        # We prefer actual product pages for the summary
        if "amazon" in url or "amazon" in title.lower():
             amazon_candidates.append(cand)
             seen_titles.add(title)
             
    if not amazon_candidates:
        # Fallback to any valid candidate if strictly amazon links aren't found
        # (e.g. Google Shopping result pointing to Amazon but url is googleadservices...)
        amazon_candidates = candidates[:5]
        
    summary = f"📦 **Amazon {config['name']} Search Results for '{query}':**\n"
    
    count = 0
    for item in amazon_candidates:
        title = item.get("title", "Unknown")
        
        # Price
        price_obj = item.get("price") or {}
        price = price_obj.get("value") or price_obj.get("current") or price_obj.get("displayed_price")
        if not price:
            # Try snippet extraction
            import re
            snippet = item.get("description") or item.get("snippet") or ""
            sym = re.escape(config["currency_symbol"])
            p_match = re.search(fr'{sym}(\d+\.?\d*)', snippet)
            if p_match: price = f"{config['currency_symbol']}{p_match.group(1)}"
            else: price = "Price Check Required"
        else:
            if str(price).replace('.','',1).isdigit():
                price = f"{config['currency_symbol']}{price}"
                
        rating_obj = item.get("rating") or {}
        rating = rating_obj.get("value", "N/A")
        
        summary += f"- **{title}**\n  Price: {price} | Rating: {rating}⭐\n"
        count += 1
        if count >= 5: break
        
    return summary

def check_amazon_stock(product_name: str, variant_details: str, region: str = "UK") -> str:
    """
    Checks stock availability/price for a specific product by querying Google Shopping Graph via Organic SERP.
    
    Args:
        product_name: General name (e.g. "Hiking Boots")
        variant_details: Specifics (e.g. "Size 10, Red")
        region: "UK" or "IN"
    """
    query = f"{product_name} {variant_details}"
    candidates = _fetch_amazon_candidates(query, region=region)
    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    if not candidates:
        return f"⚠️ Stock Check Failed: No available items found for '{query}' in {config['name']}."
        
    # Filter for Amazon-specific or highly relevant matches
    product_matches = []
    search_matches = []
    other_matches = []
    
    for cand in candidates:
        url = (cand.get("product_url") or cand.get("link") or cand.get("url") or "").lower()
        title = (cand.get("title") or "").lower()
        
        # Helper to detect if it's likely an Amazon product page
        is_amazon_url = "amazon" in url
        is_product_page = "/dp/" in url or "/gp/product/" in url
        
        if is_amazon_url:
            if is_product_page:
                product_matches.append(cand)
            elif "/s?k=" in url or "/b?" in url:
                search_matches.append(cand)
            else:
                other_matches.append(cand)
        elif "amazon" in title: 
                other_matches.append(cand)

    valid_candidates = product_matches + other_matches + search_matches
    if not valid_candidates and candidates:
            # Fallback
            valid_candidates = candidates

    best_match = None
    
    if valid_candidates:
        scored_candidates = []
        for cand in valid_candidates:
            # 1. Extract Rating (Default to 0.0)
            try:
                rating_data = cand.get("rating") or {}
                rating_val = rating_data.get("value")
                if not rating_val:
                    rating_val = 0.0
                else:
                    rating_val = float(rating_val)
            except (ValueError, TypeError):
                rating_val = 0.0
            
            # 2. Extract Delivery/Prime Status from Snippet/Title
            snippet = (cand.get("description") or cand.get("snippet") or "").lower()
            title = (cand.get("title") or "").lower()
            
            delivery_bonus = 0.0
            if "prime" in snippet or "prime" in title:
                delivery_bonus += 0.3 # Boost for Prime
            if "tomorrow" in snippet or "next day" in snippet:
                delivery_bonus += 0.2 # Boost for speed
            if "free delivery" in snippet:
                delivery_bonus += 0.1 # Small boost
            
            # 3. Calculate Final Score
            # Rule: Prefer 4+ stars. Among 4+ stars, prefer highest rating count.
            # ENHANCEMENT: Also heavily prioritize brand matches.
            is_4_plus = 1.0 if rating_val >= 4.0 else 0.0
            rating_count = cand.get("votes_count") or cand.get("rating_count") or cand.get("reviews_count") or 0
            
            # Brand Match logic
            brand_bonus = 0
            # Try to extract a potential brand from product_name (first word is a good heuristic)
            brand_query = product_name.split()[0].lower()
            if brand_query in title:
                brand_bonus = 5000000 # Significant boost for brand match
            
            # Score = (brand bonus) + (4+ bonus) + (rating count as tiebreaker)
            score = brand_bonus + (is_4_plus * 1000000) + rating_count
            
            scored_candidates.append({
                "candidate": cand,
                "score": score,
                "rating": rating_val,
                "rating_count": rating_count,
                "delivery_bonus": delivery_bonus,
                "is_brand_match": brand_bonus > 0
            })
        
        # Sort by Score Descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        # Pick top
        best_match = scored_candidates[0]["candidate"]
        
    if best_match:
        title = best_match.get("title", "Unknown Product")
        
        # Price Extraction
        price_obj = best_match.get("price") or {}
        current_price = price_obj.get('current')
        price_str = price_obj.get("displayed_price")
        
        symbol = config["currency_symbol"]

        if not price_str and current_price:
            price_str = f"{symbol}{current_price}"
        
        # Fallback for organic items which store description/snippet
        snippet = best_match.get("description") or best_match.get("snippet") or ""
        
        # If still no price, try to regex it from snippet or set as estimate
        if not price_str:
            import re
            sym = re.escape(symbol)
            # Simple regex for £XX.XX or ₹XX.XX
            p_match = re.search(fr'{sym}(\d+\.?\d*)', snippet)
            if p_match:
                price_str = f"{symbol}{p_match.group(1)}"
            else:
                price_str = "See Link (Est. Price)"

        seller_name = best_match.get("seller") or best_match.get("source") or "Amazon"
        
        # Extract Image and URL
        image_url = best_match.get("thumbnail") or best_match.get("image_url")
        
        # Guard against product URL being used as image URL (common in some DataForSEO blocks)
        if image_url and ('amazon.' in image_url and ('/dp/' in image_url or '/gp/' in image_url)):
            image_url = None
            
        product_url = best_match.get("product_url") or best_match.get("link") or best_match.get("url") or ""
        
        rating_obj = best_match.get("rating") or {}
        rating = rating_obj.get("value")
        rating_count = (rating_obj.get("votes_count") or rating_obj.get("rating_count") or rating_obj.get("reviews_count") or 
                        best_match.get("votes_count") or best_match.get("rating_count") or best_match.get("reviews_count") or 0)
        
        rating_str = f"Rating: {rating}⭐" if rating else ""
        if rating and rating_count:
            rating_str = f"Rating: {rating}⭐ ({rating_count} ratings)"
        
        # Add delivery info to output if detected
        delivery_info = ""
        if "prime" in snippet.lower():
            delivery_info = " (Prime Delivery 🚚)"
            
        # Quality Marker
        is_high_rating = rating and rating >= 4.0
        has_enough_votes = rating_count and rating_count >= 5
        
        if is_high_rating and has_enough_votes:
            quality_marker = "✅ **High Quality Match**"
        elif not rating or rating == 0 or not rating_count or rating_count == 0:
            quality_marker = "⚠️ **Quality Unverified**"
        else:
            quality_marker = "⚠️ **Lower Quality Match**"

        # Fetch reviews for the winner to pass to agent
        reviews = []
        asin = best_match.get("asin")
        if not asin and product_url:
            import re
            match = re.search(r'/dp/([A-Z0-9]{10})', product_url)
            if match: asin = match.group(1)
        
        if asin:
            reviews = _fetch_amazon_reviews(asin, region=region)

        return (f"{quality_marker} ({config['name']})\n"
                f"Item: {title}\n"
                f"Price: {price_str} (via {seller_name})\n"
                f"{rating_str}{delivery_info}\n"
                f"Reviews: {json.dumps(reviews)}\n"
                f"Full Details:\n"
                f"- Image URL: {image_url}\n"
                f"- Product URL: {product_url}\n"
                f"- Rating Count: {rating_count}\n"
                f"Match: Found via {(best_match.get('type','unknown')).title()}.")
    else:
            return (f"⚠️ **Check Required**\n"
                    f"Status: Could not verify exact stock via API.\n"
                    f"Recommendation: High likelihood of availability on Amazon {config['name']}, but exact price unavailable.")
def _fetch_amazon_reviews(asin: str, region: str = "UK") -> list:
    """
    Fetch up to 10 reviews for a specific Amazon ASID/ASIN.
    """
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return []

    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    endpoint = "https://api.dataforseo.com/v3/merchant/amazon/reviews/live"
    payload = [{
        "asin": asin,
        "location_code": config["location_code"],
        "language_code": "en"
    }]
    
    headers = _get_auth_header()
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        data = response.json()
        
        if data.get("status_code") == 20000:
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                items = tasks[0]["result"][0].get("items", [])
                reviews = []
                for item in items:
                    reviews.append({
                        "text": item.get("review_text", ""),
                        "rating": item.get("rating", {}).get("value", 0),
                        "title": item.get("review_title", ""),
                        "author": item.get("user_name", "Anonymous")
                    })
                return reviews[:10]
    except Exception as e:
        logger.error(f"Failed to fetch reviews for ASIN {asin}: {e}")
    
    return []

def search_amazon_with_reviews(query: str, region: str = "UK") -> str:
    """
    Searches for clothing/shoe items and returns a JSON block with candidates,
    each including ratings and historical reviews.
    Ordered by most ratings first, all above 4 stars.
    """
    candidates = _fetch_amazon_candidates(query, region=region)
    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    
    if not candidates:
        return f"No products found for '{query}'."

    # Filter for 4+ stars and sort by rating count
    valid_products = []
    for cand in candidates:
        rating_obj = cand.get("rating") or {}
        rating = float(rating_obj.get("value") or 0)
        votes = int(rating_obj.get("votes_count") or rating_obj.get("rating_count") or 0)
        
        if rating >= 4.0:
            valid_products.append({
                "title": cand.get("title", "Unknown"),
                "price": cand.get("price", {}).get("value") or cand.get("price", {}).get("displayed_price") or "Price Check Required",
                "rating": rating,
                "rating_count": votes,
                "url": cand.get("product_url") or cand.get("link") or cand.get("url"),
                "thumbnail": cand.get("thumbnail") or cand.get("image_url"),
                "asin": cand.get("asin"), # DataForSEO often provides ASIN in Merchant API
                "type": cand.get("type")
            })

    # Sort by votes count descending
    valid_products.sort(key=lambda x: x["rating_count"], reverse=True)
    
    logger.info(f"search_amazon_with_reviews: Found {len(valid_products)} valid products for '{query}'.")

    # Take top 3-5 candidates and fetch reviews in parallel
    from concurrent.futures import ThreadPoolExecutor
    
    results = []
    candidates_to_fetch = valid_products[:5]
    
    def fetch_with_reviews(prod):
        # If ASIN missing, try to extract from URL
        asin = prod.get("asin")
        if not asin and prod.get("url"):
            import re
            match = re.search(r'/dp/([A-Z0-9]{10})', prod["url"])
            if match:
                asin = match.group(1)
        
        reviews = []
        if asin:
            reviews = _fetch_amazon_reviews(asin, region=region)
        
        prod["reviews"] = reviews
        # variants placeholder (could be enhanced if API supports)
        prod["variants"] = [prod["thumbnail"]] if prod.get("thumbnail") else []
        return prod

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(fetch_with_reviews, candidates_to_fetch))

    if not results:
        logger.warning(f"search_amazon_with_reviews: No 4+ star results for '{query}'.")
        return f"No 4+ star products found for '{query}'."

    logger.info(f"search_amazon_with_reviews: Returning {len(results)} candidates for '{query}'.")
    # Return as structured JSON for the agent to use with [PROPOSE_PRODUCTS]
    return json.dumps(results)
