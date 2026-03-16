import json
from database import get_db_connection

def check():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, title, status FROM packages WHERE title LIKE '%Skiing%' ORDER BY rowid DESC LIMIT 1")
    pkg = c.fetchone()
    if not pkg:
        print("No skiing package found.")
        return
    
    print(f"PACKAGE: {pkg['title']} (ID: {pkg['id']}) - STATUS: {pkg['status']}")
    
    c.execute("SELECT name, item_type, price, status, metadata FROM package_items WHERE package_id = ?", (pkg['id'],))
    items = c.fetchall()
    
    print("\nITEMS:")
    for item in items:
        meta = json.loads(item['metadata']) if item['metadata'] else {}
        print(f"- {item['name']} ({item['item_type']}) - Price: {item['price']} - Status: {item['status']}")
        if 'stay_id' in meta:
            print(f"  > Stay ID: {meta['stay_id']}")
        elif 'hotel_id' in meta:
            print(f"  > Hotel ID: {meta['hotel_id']}")
        if 'offer_id' in meta:
            print(f"  > Offer ID: {meta['offer_id']}")
        if 'booking_link' in meta:
             print(f"  > Booking Link: {meta['booking_link']}")
        if 'booking_reference' in meta:
            print(f"  > Booking Ref: {meta['booking_reference']}")

    conn.close()

if __name__ == '__main__':
    check()
