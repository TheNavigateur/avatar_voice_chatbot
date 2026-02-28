import sqlite3
import json
import os

DB_NAME = "app.db"

def dump_latest_package():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get latest package
    c.execute("SELECT * FROM packages ORDER BY ROWID DESC LIMIT 1")
    pkg = c.fetchone()
    if not pkg:
        print("No packages found.")
        return

    print(f"--- Package Details ---")
    print(f"ID: {pkg['id']}")
    print(f"Title: {pkg['title']}")
    print(f"Type: {pkg['type']}")
    print(f"Status: {pkg['status']}")
    print(f"Total Price: {pkg['total_price']}")
    print("\n--- Items ---")

    c.execute("SELECT * FROM package_items WHERE package_id = ? ORDER BY ROWID ASC", (pkg['id'],))
    items = c.fetchall()
    
    for i in items:
        print(f"Item: {i['name']} [ID: {i['id']}]")
        print(f"  Type: {i['item_type']}")
        print(f"  Price: {i['price']}")
        print(f"  Description: {i['description']}")
        print(f"  Metadata: {i['metadata']}")
        print("-" * 20)

    conn.close()

if __name__ == "__main__":
    dump_latest_package()
