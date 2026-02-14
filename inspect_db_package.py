import sqlite3
import json

def inspect_latest_package():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Get latest package
    c.execute("SELECT * FROM packages ORDER BY rowid DESC LIMIT 1")
    pkg = c.fetchone()
    
    if not pkg:
        print("No packages found.")
        return

    print(f"Package: {pkg['title']} (ID: {pkg['id']})")
    
    c.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg['id'],))
    items = c.fetchall()
    
    for item in items:
        print(f"\nItem: {item['name']}")
        print(f"  ID: {item['id']}")
        print(f"  Price: {item['price']}")
        print(f"  Metadata (Raw): {item['metadata']}")
        
        try:
            meta = json.loads(item['metadata'])
            print(f"  Metadata (JSON): {json.dumps(meta, indent=2)}")
            if 'product_url' in meta:
                print(f"  Product URL: {meta['product_url']}")
            else:
                print("  NO PRODUCT URL FOUND")
        except Exception as e:
            print(f"  Error parsing metadata: {e}")

    conn.close()

if __name__ == "__main__":
    inspect_latest_package()
