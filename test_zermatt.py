import os
import asyncio
from services.amadeus_service import AmadeusService

async def test():
    service = AmadeusService()
    # Try geocoding Zermatt
    print("Geocoding Zermatt...")
    lat, lon = service.get_coordinates("Zermatt")
    print(f"Coordinates: {lat}, {lon}")
    
    if lat:
        print("Searching hotels near coordinates for June 2026...")
        res = service.search_hotels_formatted(latitude=lat, longitude=lon, check_in="2026-06-01", check_out="2026-06-07")
        print(f"Results:\n{res}")

if __name__ == "__main__":
    asyncio.run(test())
