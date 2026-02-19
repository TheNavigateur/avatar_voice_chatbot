#!/usr/bin/env python3
"""Remove unreliable image URLs from all packages"""
import sqlite3
import json

conn = sqlite3.connect('app.db')
c = conn.cursor()

unreliable_domains = ['getyourguide.com', 'tripadvisor.com', 'viator.com', 'booking.com', 'unsplash.com']

# Get all package items with images
items = c.execute('''
    SELECT id, name, metadata, item_type
    FROM package_items
    WHERE metadata LIKE '%image_url%'
''').fetchall()

print(f"Checking {len(items)} items for unreliable images...\n")

removed_count = 0
kept_count = 0

for item_id, name, metadata_str, item_type in items:
    metadata = json.loads(metadata_str) if metadata_str else {}
    image_url = metadata.get('image_url', '')
    
    if image_url and any(domain in image_url.lower() for domain in unreliable_domains):
        print(f"❌ Removing unreliable image from: {name}")
        print(f"   URL: {image_url[:70]}...")
        
        # Remove the image_url
        del metadata['image_url']
        
        c.execute('''
            UPDATE package_items
            SET metadata = ?
            WHERE id = ?
        ''', (json.dumps(metadata), item_id))
        
        removed_count += 1
    elif image_url:
        print(f"✅ Keeping reliable image for: {name}")
        kept_count += 1

conn.commit()
conn.close()

print(f"\n🎉 Done!")
print(f"   Removed: {removed_count} unreliable images")
print(f"   Kept: {kept_count} reliable images")
print(f"\nItems without images will display cleanly without placeholders.")
