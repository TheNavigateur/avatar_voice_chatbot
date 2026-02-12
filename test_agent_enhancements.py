from services.amadeus_service import AmadeusService
from tools.search_tool import perform_google_search
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def test_agent_logic():
    svc = AmadeusService()
    
    print("\n--- Test 1: Resolve City to IATA ---")
    city = "Palma de Mallorca"
    iata = svc.resolve_city_to_iata(city)
    print(f"'{city}' -> '{iata}'")
    
    if iata == "PMI":
        print("SUCCESS: Resolved correctly.")
    else:
        print("FAILURE: Did not resolve to PMI.")

    print("\n--- Test 2: Activity Fallback Simulation ---")
    # Simulating Agent Logic
    location = "Palma de Mallorca"
    keyword = "Water Park"
    
    # 1. Amadeus (known to fail for Water Park)
    amadeus_res = svc.search_activities_formatted(location, keyword)
    print(f"Amadeus Result: {amadeus_res}")
    
    if "No activities found" in amadeus_res:
        print("Amadeus returned nothing (Expected). Testing Fallback...")
        # 2. Fallback
        query = f"{keyword} in {location}"
        print(f"Fallback Query: {query}")
        # google_res = perform_google_search(query) 
        # print(google_res[:200] + "...")
        print("Fallback logic simulation complete (assuming perform_google_search works as existing tool).")

if __name__ == "__main__":
    test_agent_logic()
