"""
Debug script to check shopping package data and display conditions
"""
import requests
import json

BASE_URL = "http://localhost:5000"

def check_packages():
    """Check all packages for user web_user"""
    print("=" * 60)
    print("CHECKING PACKAGES FOR USER: web_user")
    print("=" * 60)
    
    response = requests.get(f"{BASE_URL}/api/user/web_user/packages")
    print(f"Status Code: {response.status_code}")
    print(f"Response Text: {response.text[:200]}")
    
    if response.status_code != 200:
        print(f"ERROR: API returned status {response.status_code}")
        return []
    
    try:
        packages = response.json()
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse JSON: {e}")
        print(f"Full response: {response.text}")
        return []
    
    print(f"\nTotal packages: {len(packages)}\n")
    
    for i, pkg in enumerate(packages, 1):
        print(f"\n--- Package {i} ---")
        print(f"ID: {pkg['id']}")
        print(f"Title: {pkg['title']}")
        print(f"Type: {pkg['type']}")
        print(f"Status: {pkg['status']}")
        print(f"Total Items: {len(pkg['items'])}")
        
        # Categorize items
        product_items = [item for item in pkg['items'] if item.get('item_type') == 'product']
        travel_items = [item for item in pkg['items'] if item.get('item_type') in ['flight', 'hotel', 'activity']]
        other_items = [item for item in pkg['items'] if item not in product_items and item not in travel_items]
        
        print(f"\nItem Breakdown:")
        print(f"  - Product items: {len(product_items)}")
        print(f"  - Travel items: {len(travel_items)}")
        print(f"  - Other items: {len(other_items)}")
        
        if product_items:
            print(f"\nProduct Items:")
            for item in product_items:
                print(f"  • {item['name']} (${item['price']})")
                if item.get('metadata'):
                    print(f"    Metadata keys: {list(item['metadata'].keys())}")
        
        # Check display condition
        will_show_shopping = len(product_items) > 0 and pkg['status'] == 'booked'
        print(f"\n🛍️ Shopping Package Will Display: {will_show_shopping}")
        if not will_show_shopping:
            if len(product_items) == 0:
                print("   ❌ Reason: No product items")
            if pkg['status'] != 'booked':
                print(f"   ❌ Reason: Status is '{pkg['status']}' (needs to be 'booked')")
        
        print("-" * 60)
    
    return packages

if __name__ == "__main__":
    packages = check_packages()
    
    # Find the most recent package
    if packages:
        latest = packages[-1]
        print(f"\n{'=' * 60}")
        print(f"LATEST PACKAGE: {latest['title']}")
        print(f"This is the package that should open when agent says")
        print(f"'I'm opening your shopping package now'")
        print(f"{'=' * 60}")
