import os
import sys

# Mock environment
os.environ["DATAFORSEO_LOGIN"] = "test"
os.environ["DATAFORSEO_PASSWORD"] = "test"

# Import the tool
from tools.market_tools import check_amazon_stock
from unittest.mock import patch

# Mock data
mock_candidates = [
    {
        "title": "Minimalist Sunscreen SPF 50 Lightweight, No White Cast",
        "rating": {"value": 4.2},
        "rating_count": 27247,
        "price": {"value": 10.0, "currency": "GBP"},
        "product_url": "https://www.amazon.co.uk/dp/B09V7N8XXX",
        "type": "shopping"
    },
    {
        "title": "NIVEA SUN Sun Cream SPF 50, Pocket Size (Low rating mock)",
        "rating": {"value": 3.5},
        "rating_count": 100,
        "price": {"value": 5.0, "currency": "GBP"},
        "product_url": "https://www.amazon.co.uk/dp/B09V7N8YYY",
         "type": "shopping"
    },
    {
        "title": "NIVEA SUN Shine Control SPF 50",
        "rating": {"value": 4.5},
        "rating_count": 500,
        "price": {"value": 8.0, "currency": "GBP"},
        "product_url": "https://www.amazon.co.uk/dp/B09V7N8ZZZ",
         "type": "shopping"
    }
]

def test_brand_priority():
    print("Testing brand priority (NIVEA should win even if it has fewer reviews than Minimalist)...")
    with patch("tools.market_tools._fetch_amazon_candidates", return_value=mock_candidates):
        # We search for "NIVEA sun cream"
        result = check_amazon_stock("NIVEA sun cream", "SPF 50", region="UK")
        print(result)
        
        if "NIVEA SUN Shine Control SPF 50" in result and "4.5⭐" in result:
            print("SUCCESS: NIVEA won over Minimalist due to brand match!")
        else:
            print("FAILURE: NIVEA did not win.")

def test_minimalist_winner_if_no_nivea():
    print("\nTesting fallback when brand match is not found...")
    # Remove NIVEA matches
    only_minimalist = [mock_candidates[0]]
    with patch("tools.market_tools._fetch_amazon_candidates", return_value=only_minimalist):
        result = check_amazon_stock("NIVEA sun cream", "SPF 50", region="UK")
        print(result)
        if "Minimalist Sunscreen" in result:
            print("SUCCESS: Minimalist picked when NIVEA not found.")
        else:
            print("FAILURE: Minimalist not picked.")

if __name__ == "__main__":
    test_brand_priority()
    test_minimalist_winner_if_no_nivea()
