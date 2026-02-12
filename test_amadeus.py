from services.amadeus_service import AmadeusService
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_amadeus():
    print("Testing Amadeus Service...")
    svc = AmadeusService()
    
    if svc.amadeus:
        print("Client initialized successfully.")
    else:
        print("Client NOT initialized (expected if no keys).")
        
    print(svc.search_hotels_formatted("LON"))

if __name__ == "__main__":
    test_amadeus()
