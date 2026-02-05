import os
import requests
import json
import logging
import base64

logger = logging.getLogger(__name__)

# DataForSEO Credentials
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

BASE_URL = "https://api.dataforseo.com/v3/serp/google"

def _get_auth_header():
    if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
        return None
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def _search_organic_live(query: str):
    """Generic helper to call Organic Live Advanced"""
    endpoint = f"{BASE_URL}/organic/live/advanced"
    payload = [{
        "keyword": query,
        "location_code": 2840, # Default US (DataForSEO creates separate engines per location)
        # Maybe we should let user specify? For now hardcoded or global.
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

def search_products(query: str) -> str:
    """
    Search for products via Organic SERP (Shopping Results).
    """
    query_str = f"buy {query}"
    items, error = _search_organic_live(query_str)
    
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
        if not price and "£" in item.get("description", ""):
            # simple extract
            desc = item.get("description", "")
            # (Very basic extraction logic here, agent will have to interpret)
            price = "See Link"
            
        summary += f"- {title} - {price} - [Link]({link})\n"
        count += 1
        if count >= 5: break
        
    return summary
