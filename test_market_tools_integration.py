
import os
import sys
import logging

# Setup logging
logging.basicConfig(level=logging.ERROR)
sys.path.append(os.getcwd())

from tools.market_tools import search_flights, search_hotels, search_products

def test_integration():
    print("--- INTEGRATION TEST ---")
    
    # 1. FLIGHTS
    print("\n[1] Testing Flights...")
    res = search_flights("LHR", "JFK", "2025-05-01")
    print(f"Result (truncated): {res[:200]}...")
    
    # 2. HOTELS
    print("\n[2] Testing Hotels...")
    res = search_hotels("London", "2025-06-01", "2025-06-02")
    print(f"Result (truncated): {res[:200]}...")
    
    # 3. PRODUCTS
    print("\n[3] Testing Products...")
    res = search_products("sun cream")
    print(f"Result (truncated): {res[:200]}...")

if __name__ == "__main__":
    if not os.environ.get("DATAFORSEO_LOGIN"):
        print("Set creds first")
    else:
        test_integration()
