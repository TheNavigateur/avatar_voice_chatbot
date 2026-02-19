import os
import sys
import json

# Add current directory to path so we can import tools
sys.path.append(os.getcwd())

from tools.market_tools import _fetch_amazon_candidates

def reproduce():
    import requests
    import base64
    
    query = "MGGMOKAY Sandals"
    config = {"location_code": 2826, "tld": "co.uk"}
    full_query = f"{query} site:amazon.{config['tld']}"
    
    DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
    DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
    
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
    
    url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
    payload = [{
        "keyword": full_query,
        "location_code": config["location_code"], 
        "language_code": "en",
        "depth": 50
    }]
    
    print(f"Fetching raw data for query: {full_query}")
    res = requests.post(url, headers=headers, json=payload)
    data = res.json()
    
    with open("raw_dataforseo_response.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Saved raw response to raw_dataforseo_response.json")

    # Now use the existing candidates logic or just parse data here
    items = []
    if data.get("tasks") and data["tasks"][0].get("result"):
        items = data["tasks"][0]["result"][0].get("items", [])
    
    candidates = []
    for item in items:
        if item.get("type") == "popular_products":
            sub_items = item.get("items")
            if sub_items:
                for sub_item in sub_items:
                    candidates.append(sub_item)
        elif item.get("type") in ["shopping", "organic", "shopping_results"]:
            candidates.append(item)
            
    found = False
    for cand in candidates:
        url = cand.get("product_url") or cand.get("link") or cand.get("url") or ""
        title = cand.get("title", "")
        rating = cand.get("rating")
        
        if "B0DY1DPX55" in url or "MGGMOKAY" in title:
            found = True
            print(f"Found product: {title}")
            print(f"URL: {url}")
            print(f"Rating: {json.dumps(rating, indent=2)}")
            print(f"Type: {cand.get('type')}")
            
    if not found:
        print("Product B0DY1DPX55 not found in search results.")
        # Try searching by ASIN directly
        print("\nTrying search by ASIN...")
        candidates_asin = _fetch_amazon_candidates("B0DY1DPX55", region="UK")
        for cand in candidates_asin:
            url = cand.get("product_url") or cand.get("link") or cand.get("url") or ""
            if "B0DY1DPX55" in url:
                print(f"Found product via ASIN: {cand.get('title')}")
                rating = cand.get("rating")
                print(f"Rating object: {json.dumps(rating, indent=2)}")

if __name__ == "__main__":
    reproduce()
