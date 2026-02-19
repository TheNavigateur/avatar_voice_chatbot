import os
import sys
import json
import requests
import base64

# Add current directory to path so we can import tools
sys.path.append(os.getcwd())

from tools.market_tools import _fetch_amazon_reviews, _get_auth_header

def test_reviews():
    asin = "B0DY1DPX55"
    region = "UK"
    print(f"Fetching reviews for ASIN: {asin}")
    
    reviews = _fetch_amazon_reviews(asin, region=region)
    print(f"Fetched {len(reviews)} reviews.")
    for i, r in enumerate(reviews):
        print(f"Review {i+1}: {r.get('rating')} stars - {r.get('title')}")
        
    # Also check raw merchant response if possible
    DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
    DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
    headers = _get_auth_header()
    
    endpoint = "https://api.dataforseo.com/v3/merchant/amazon/reviews/live"
    payload = [{
        "asin": asin,
        "location_code": 2826, # UK
        "language_code": "en"
    }]
    
    print("\nFetching raw merchant reviews data...")
    response = requests.post(endpoint, headers=headers, json=payload)
    data = response.json()
    with open("raw_reviews_response.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Saved raw reviews response to raw_reviews_response.json")

if __name__ == "__main__":
    test_reviews()
