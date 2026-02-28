import os
import requests
import logging
from services.amadeus_service import AmadeusService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from services.duffel_service import DuffelService
def test_iata_resolution():
    service = DuffelService()
    city = "Doha"
    url = f"{service.BASE_URL}/air/places/suggestions?query={city}"
    # Wait, I used /air/places/suggestions in my previous unsuccessful attempt (404).
    # But in Step 180 I said I'll try /places/suggestions.
    # Let's check what I actually did in Step 179.
    # Step 179: url = f"{service.BASE_URL}/places/suggestions?query={city}"
    # Step 183 output: Status 200.
    # So /air prefix is NOT needed or it's just /places/suggestions?
    # Wait, Step 183 output shows a lot of places.
    
    url = f"{service.BASE_URL}/air/places/suggestions?query={city}"
    # Wait, if I got 404 for /air/places/suggestions, then it's definitely /places/suggestions.
    
    url = f"{service.BASE_URL}/places/suggestions?query={city}"
    resp = requests.get(url, headers=service.headers)
    data = resp.json().get("data", [])
    if data:
        print(f"City: {city} -> IATA: {data[0].get('iata_code')}")
    else:
        print(f"City: {city} -> Not found")

if __name__ == "__main__":
    test_iata_resolution()
