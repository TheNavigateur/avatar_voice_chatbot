from services.amadeus_service import AmadeusService
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def debug_palma():
    svc = AmadeusService()
    location = "Palma de Mallorca"
    
    print(f"\n--- Debugging Activities for '{location}' ---")
    # Test Geocoding
    lat, lon = svc.get_coordinates(location)
    print(f"Geocoding Result: {lat}, {lon}")
    
    if lat:
        # Test POI Search (better for 'places' like water parks?)
        print(f"\nSearching POIs near {lat}, {lon}...")
        try:
            # reference_data.locations.points_of_interest
            pois = svc.amadeus.reference_data.locations.points_of_interest.get(
                latitude=lat,
                longitude=lon,
                radius=10,
                categories='SIGHTS,NIGHTLIFE,RESTAURANT,SHOPPING' # limited categories in amadeus?
            )
            print("POI Results (Raw):")
            # print(pois.data[:3]) 
            # Filter manually for "water"
            for p in pois.data:
                name = p.get('name', '').lower()
                category = p.get('category', '')
                if 'water' in name or 'park' in name:
                    print(f"Match: {p['name']} ({category})")
        except Exception as e:
            print(f"POI Error: {e}")

        # Test Activity Search
        print(f"\nSearching tours/activities near {lat}, {lon}...")
        results = svc.search_activities_formatted(location, "water park")
        print("Water Park Results:")
        print(results)
        
        results_gen = svc.search_activities_formatted(location)
        print("General Results (Top 5):")
        print(results_gen[:500] + "...")

    print(f"\n--- Debugging Hotels for '{location}' ---")
    # Current agent logic skips Amadeus if not 3 chars.
    # checking if we can resolve it to IATA
    try:
        # Try to find IATA code
        resp = svc.amadeus.reference_data.locations.get(
            keyword=location,
            subType='CITY'
        )
        if resp.data:
            print("Found Location Data:")
            print(resp.data[0])
            iata = resp.data[0].get('iataCode')
            print(f"Derived IATA Code: {iata}")
            
            if iata:
                print(f"Searching hotels for IATA: {iata}")
                hotels = svc.search_hotels_formatted(iata)
                print(hotels[:500] + "...")
        else:
            print("No location data found in Amadeus.")
            
    except Exception as e:
        print(f"Location Search Error: {e}")

if __name__ == "__main__":
    debug_palma()
