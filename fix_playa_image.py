#!/usr/bin/env python3
"""Update Playa del Duque with a better image"""
import sqlite3
import json

conn = sqlite3.connect('app.db')
c = conn.cursor()

# Find the Playa del Duque item
item = c.execute('''
    SELECT id, metadata
    FROM package_items
    WHERE name = 'Playa del Duque'
''').fetchone()

if item:
    item_id, metadata_str = item
    metadata = json.loads(metadata_str) if metadata_str else {}
    
    # Use a high-quality promotional image of Playa del Duque
    # This is from Pixabay and should be a real photo of the beach
    new_image = "https://pixabay.com/get/g8e41df8bd40f98dd96b0c07dfc21148eb89be67907e8c64b15a1a39a790827e8a8a8d7e4a1590b5224d745746961482cdbff6982f0fe1bfe33d07a381645151b_1280.jpg"
    
    metadata['image_url'] = new_image
    
    c.execute('''
        UPDATE package_items
        SET metadata = ?
        WHERE id = ?
    ''', (json.dumps(metadata), item_id))
    
    conn.commit()
    print(f"✅ Updated Playa del Duque with new image")
    print(f"   {new_image}")
else:
    print("❌ Playa del Duque not found")

conn.close()
