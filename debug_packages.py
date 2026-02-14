import sqlite3
import json

def get_packages():
    conn = sqlite3.connect('app.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM packages")
    packages = cursor.fetchall()
    
    for pkg in packages:
        print(f"\nPackage: {pkg['title']} (ID: {pkg['id']}, Type: {pkg['type']})")
        
        cursor.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg['id'],))
        items = cursor.fetchall()
        
        if not items:
            print("  No items.")
        else:
            for item in items:
                print(f"  - [{item['item_type']}] {item['name']} (${item['price']})")

    conn.close()

if __name__ == "__main__":
    get_packages()
