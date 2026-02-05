
import os
import sys
import logging
from tools.market_tools import search_hotels

# Setup logging
logging.basicConfig(level=logging.INFO)
sys.path.append(os.getcwd())

def debug_hotel_search():
    print("--- DEBUG HOTEL SEARCH ---")
    # Simulate a search for next weekend
    location = "Paris"
    check_in = "2026-02-13" # Next Friday
    check_out = "2026-02-15" # Next Sunday
    
    print(f"Querying for: {location}, {check_in} to {check_out}")
    # We need to call the internal _search_organic_live to see raw json, 
    # but that is hidden. Let's just import requests and do it manually here.
    import requests
    import base64
    import json
    
    DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
    DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    
    endpoint = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": f"hotels in {location} from {check_in} to {check_out}",
        "location_code": 2840,
        "language_code": "en"
    }]
    
    resp = requests.post(endpoint, headers=headers, json=payload)
    data = resp.json()
    
    try:
        items = data['tasks'][0]['result'][0]['items']
        for item in items:
            if item.get("type") == "hotels_pack":
                print("\n--- FOUND HOTEL PACK ---")
                # Print first hotel item in the pack
                if item.get("items"):
                    print(json.dumps(item["items"][0], indent=2))
                break
    except Exception as e:
        print(f"Error parsing raw: {e}")
        
    # result = search_hotels(location, check_in, check_out)
    # print("\n--- OLD RESULT ---")
    # print(result)

if __name__ == "__main__":
    if not os.environ.get("DATAFORSEO_LOGIN"):
        print("Error: Set creds first")
    else:
        debug_hotel_search()
