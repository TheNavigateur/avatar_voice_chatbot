"""
Direct database check for shopping package data
"""
import sqlite3
import json

DB_PATH = "app.db"

def check_database():
    """Check packages directly from database"""
    print("=" * 60)
    print("CHECKING DATABASE DIRECTLY")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all packages
    cursor.execute("SELECT id, session_id, user_id, title, type, status, total_price FROM packages")
    rows = cursor.fetchall()
    
    print(f"\nTotal packages in DB: {len(rows)}\n")
    
    for row in rows:
        pkg_id, session_id, user_id, title, pkg_type, status, total_price = row
        
        # Get items for this package
        cursor.execute("SELECT name, item_type, price, metadata FROM package_items WHERE package_id = ?", (pkg_id,))
        item_rows = cursor.fetchall()
        items = []
        for item in item_rows:
            name, item_type, price, metadata_json = item
            metadata = json.loads(metadata_json) if metadata_json else {}
            items.append({"name": name, "item_type": item_type, "price": price, "metadata": metadata})
        
        print(f"\n--- Package ---")
        print(f"ID: {pkg_id}")
        print(f"User ID: {user_id}")
        print(f"Session ID: {session_id}")
        print(f"Title: {title}")
        print(f"Type: {pkg_type}")
        print(f"Status: {status}")
        print(f"Total Items: {len(items)}")
        
        # Categorize items
        product_items = [item for item in items if item.get('item_type') == 'product']
        travel_items = [item for item in items if item.get('item_type') in ['flight', 'hotel', 'activity']]
        
        print(f"\nItem Breakdown:")
        print(f"  - Product items: {len(product_items)}")
        print(f"  - Travel items: {len(travel_items)}")
        
        if product_items:
            print(f"\n📦 Product Items:")
            for item in product_items:
                print(f"  • {item['name']} (${item['price']})")
                if item.get('metadata'):
                    print(f"    Has metadata: {list(item['metadata'].keys())}")
        
        # Check display condition
        will_show_shopping = len(product_items) > 0 and status == 'booked'
        print(f"\n🛍️ Shopping Package Will Display: {will_show_shopping}")
        if not will_show_shopping:
            if len(product_items) == 0:
                print("   ❌ Reason: No product items")
            if status != 'booked':
                print(f"   ❌ Reason: Status is '{status}' (needs to be 'booked')")
        
        print("-" * 60)
    
    conn.close()
    
    # Check for web_user specifically
    print(f"\n{'=' * 60}")
    print("PACKAGES FOR USER: web_user")
    print(f"{'=' * 60}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, status FROM packages WHERE user_id = 'web_user' OR user_id IS NULL OR user_id = '' ORDER BY rowid DESC")
    web_user_packages = cursor.fetchall()
    
    if not web_user_packages:
        print("❌ NO PACKAGES FOUND FOR web_user")
    else:
        print(f"Found {len(web_user_packages)} packages for web_user")
        latest = web_user_packages[0]
        pkg_id, title, status = latest
        
        # Get items for latest
        cursor.execute("SELECT item_type FROM package_items WHERE package_id = ?", (pkg_id,))
        item_types = [r[0] for r in cursor.fetchall()]
        product_count = sum(1 for t in item_types if t == 'product')
        
        print(f"\nLatest Package: {title}")
        print(f"Status: {status}")
        print(f"Product items: {len(product_items)}")
        
        if len(product_items) > 0 and status == 'booked':
            print("✅ This package SHOULD show the shopping section!")
        else:
            print("❌ This package will NOT show the shopping section")
            if status != 'booked':
                print(f"   Need to book it (current status: {status})")
            if len(product_items) == 0:
                print("   Need to add product items")
    
    conn.close()

if __name__ == "__main__":
    check_database()
