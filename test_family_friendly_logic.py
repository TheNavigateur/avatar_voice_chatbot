from services.amadeus_service import AmadeusService
import logging
import sys
import os

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_family_friendly():
    print("Testing Family Friendly Activity Logic...")
    svc = AmadeusService()
    
    # Test 1: London with 'family friendly' keyword
    print("\n--- Searching 'family friendly' in London ---")
    results = svc.search_activities_formatted("London", "family friendly")
    print(results)
    
    # Test 2: London with 'kids' keyword
    print("\n--- Searching 'kids' in London ---")
    results_kids = svc.search_activities_formatted("London", "kids")
    print(results_kids)

    # Test 3: Dubai with 'family friendly' (likely to have water parks)
    print("\n--- Searching 'family friendly' in Dubai ---")
    results_dubai = svc.search_activities_formatted("Dubai", "family friendly")
    print(results_dubai)

if __name__ == "__main__":
    if not os.environ.get("AMADEUS_CLIENT_ID"):
        print("Error: AMADEUS_CLIENT_ID not set. Please source secrets.sh")
    else:
        test_family_friendly()
