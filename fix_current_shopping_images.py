import sqlite3
import json
import os
import sys

# Add current directory to path for imports
sys.path.append(os.getcwd())

from services.image_search_service import ImageSearchService

def fix_shopping_images():
    db_path = 'app.db'
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find items with potentially broken images: "unknown", product URLs, or missing images
    # We focus on 'product' or 'shopping' item types
    items = c.execute('''
        SELECT id, name, metadata 
        FROM package_items 
        WHERE item_type IN ('product', 'shopping')
    ''').fetchall()

    image_service = ImageSearchService()
    fixed_count = 0

    for item in items:
        item_id = item['id']
        name = item['name']
        metadata = json.loads(item['metadata']) if item['metadata'] else {}
        
        image_url = metadata.get('image_url', '')
        images = metadata.get('images', [])
        
        needs_fix = False
        
        # Check if primary image_url is "broken"
        if not image_url or image_url == 'unknown' or 'amazon.co.uk/dp/' in image_url or 'amazon.com/dp/' in image_url:
            needs_fix = True
        
        # Check if images list is empty or contains bad URLs
        if not images or all(img == 'unknown' or 'amazon' in img and '/dp/' in img for img in images):
            needs_fix = True

        if needs_fix:
            print(f"🔧 Fixing image for: {name} (Current: {image_url})")
            
            # Use general image search as get_product_image isn't added yet, 
            # or just use search_image_multi
            new_images = image_service.search_image_multi(f"{name} product", num=3, prefer_google=True)
            
            if new_images:
                metadata['image_url'] = new_images[0]
                metadata['images'] = new_images
                
                c.execute('''
                    UPDATE package_items 
                    SET metadata = ? 
                    WHERE id = ?
                ''', (json.dumps(metadata), item_id))
                
                print(f"  ✅ Fixed with: {new_images[0]}")
                fixed_count += 1
            else:
                print(f"  ❌ Failed to find new image for: {name}")

    conn.commit()
    conn.close()
    print(f"\nFinished. Fixed {fixed_count} items.")

if __name__ == "__main__":
    fix_shopping_images()
