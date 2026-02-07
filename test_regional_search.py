
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from tools.market_tools import search_amazon, check_amazon_stock, AMAZON_REGIONS

def test_regional_search():
    print("🚀 Starting Regional Search Verification...")
    
    # Test UK
    print("\n--------------------------------------------------")
    print("🇬🇧 Testing UK Region...")
    uk_res = search_amazon("imac pro", region="UK")
    print(f"Result Preview: {uk_res[:200]}...")
    
    if "£" in uk_res:
        print("✅ UK Currency Symbol Found")
    else:
        print("❌ UK Currency Symbol MISSING")
        
    if "amazon.co.uk" in uk_res:
        print("✅ UK Domain Found")
    else:
        print("❌ UK Domain MISSING")
        
    # Test India
    print("\n--------------------------------------------------")
    print("🇮🇳 Testing India Region...")
    in_res = search_amazon("imac pro", region="IN")
    print(f"Result Preview: {in_res[:200]}...")
    
    if "₹" in in_res:
        print("✅ India Currency Symbol Found")
    else:
        print("❌ India Currency Symbol MISSING")
        
    if "amazon.in" in in_res:
        print("✅ India Domain Found")
    else:
        print("❌ India Domain MISSING")

    # Test Stock Check UK
    print("\n--------------------------------------------------")
    print("🇬🇧 Testing Stock Check UK...")
    uk_stock = check_amazon_stock("MacBook Air M2", "silver", region="UK")
    print(f"Result: {uk_stock}")
    
    # Test Stock Check India
    print("\n--------------------------------------------------")
    print("🇮🇳 Testing Stock Check India...")
    in_stock = check_amazon_stock("MacBook Air M2", "silver", region="IN")
    print(f"Result: {in_stock}")

if __name__ == "__main__":
    test_regional_search()
