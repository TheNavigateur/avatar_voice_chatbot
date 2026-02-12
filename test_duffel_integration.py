from services.duffel_service import DuffelService
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_flight_search():
    duffel = DuffelService()
    print("Testing Duffel Flight Search...")
    
    # Search LHR to JFK for tomorrow (or a near future date)
    from datetime import datetime, timedelta
    tomorrow = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
    
    try:
        results = duffel.search_flights_formatted("LHR", "JFK", tomorrow)
        print("\n--- Flight Results ---")
        print(results)
    except Exception as e:
        print(f"Flight Error: {e}")

    print("\nTesting Duffel Hotel Search (London)...")
    try:
        # Check for 2 nights from tomorrow
        check_out = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        hotel_results = duffel.search_hotels("London", tomorrow, check_out)
        print("\n--- Hotel Results ---")
        print(hotel_results)
    except Exception as e:
        print(f"Hotel Error: {e}")

if __name__ == "__main__":
    test_flight_search()
