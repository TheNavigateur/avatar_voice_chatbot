from services.amadeus_service import AmadeusService
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_activities():
    print("Testing Amadeus Activities Service...")
    svc = AmadeusService()
    
    # Test 1: Geocoding
    lat, lon = svc.get_coordinates("Dubai")
    print(f"Geocoding 'Dubai': {lat}, {lon}")
    
    # Test 2: Activities in London
    print("\n--- Searching 'London Tower' in London ---")
    results = svc.search_activities_formatted("London", "Tower")
    print(results)

    # Test 3: Broad search (Dubai)
    print("\n--- Searching Activities in Dubai ---")
    results_dubai = svc.search_activities_formatted("Dubai")
    print(results_dubai)

if __name__ == "__main__":
    test_activities()
