from services.duffel_service import DuffelService
import json

def test_search():
    print("Initializing Duffel Service...")
    service = DuffelService()
    
    if not service.client:
        print("Skipping test: No API Token")
        return

    print("Searching for flights LHR -> JFK (3 days from now)...")
    # Dynamic date? Let's just hardcode a future date for now or calc it
    from datetime import date, timedelta
    future_date = (date.today() + timedelta(days=30)).isoformat()
    
    results = service.search_flights_oneway("LHR", "JFK", future_date)
    
    print(f"Found {len(results)} offers.")
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    test_search()
