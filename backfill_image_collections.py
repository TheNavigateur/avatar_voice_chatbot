#!/usr/bin/env python3
import os
import sys
import sqlite3
import json
import logging
import subprocess
from typing import List, Optional

# Add current directory to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment (API keys)
if os.path.exists('secrets.sh'):
    logger.info("Loading environment from secrets.sh...")
    result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd=os.getcwd())
    for line in result.stdout.split('\n'):
        if '=' in line:
            parts = line.split('=', 1)
            if len(parts) == 2:
                key, value = parts
                os.environ[key] = value

from services.image_search_service import ImageSearchService

def backfill_image_collections():
    service = ImageSearchService()
    db_path = 'app.db'
    
    if not os.path.exists(db_path):
        logger.error(f"Database {db_path} not found")
        return

    # Use a longer timeout for database lock
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, name, item_type, metadata FROM package_items")
    items = cursor.fetchall()
    
    logger.info(f"Checking {len(items)} items for image collections...")
    
    updated_count = 0
    skipped_count = 0
    
    for item in items:
        item_id = item['id']
        name = item['name']
        item_type = item['item_type']
        metadata_str = item['metadata']
        
        metadata = json.loads(metadata_str) if metadata_str else {}
        images = metadata.get('images', [])
        image_url = metadata.get('image_url', '')
        
        # If images list is missing or has very few items, backfill it
        if not images or len(images) < 3:
            logger.info(f"🖼️ Backfilling images for '{name}' ({item_type})")
            
            found_images = []
            try:
                if item_type == 'hotel':
                    found_images = service.get_hotel_image(name, num=5)
                elif item_type == 'activity':
                    # Get package title for location context if possible
                    cursor.execute("SELECT title FROM packages p JOIN package_items pi ON p.id = pi.package_id WHERE pi.id = ?", (item_id,))
                    pkg_row = cursor.fetchone()
                    location = None
                    if pkg_row:
                        location = pkg_row['title'].replace('Holiday', '').replace('Trip', '').replace('Getaway', '').strip()
                    found_images = service.get_activity_image(name, location, num=5)
                elif item_type == 'flight':
                    found_images = service.get_flight_image(name, num=5)
                else:
                    found_images = service.search_image_multi(name, num=5)
            except Exception as e:
                logger.error(f"  ❌ Search failed for {name}: {e}")
                continue
            
            if found_images:
                # Merge with existing image_url if not present
                if image_url and image_url not in found_images:
                    found_images = [image_url] + found_images
                
                # Deduplicate and limit
                unique_images = []
                for img in found_images:
                    if img not in unique_images:
                        unique_images.append(img)
                unique_images = unique_images[:5]
                
                metadata['images'] = unique_images
                if not metadata.get('image_url') and unique_images:
                    metadata['image_url'] = unique_images[0]
                
                try:
                    cursor.execute("UPDATE package_items SET metadata = ? WHERE id = ?", (json.dumps(metadata), item_id))
                    updated_count += 1
                    logger.info(f"  ✅ Added {len(unique_images)} images")
                except sqlite3.OperationalError as e:
                    logger.error(f"  ❌ Database error updating {name}: {e}")
                    # Try to commit what we have so far if it's a lock issue
                    conn.commit()
            else:
                logger.warning(f"  ⚠️ No images found for: {name}")
                skipped_count += 1
        else:
            skipped_count += 1
            
        # Periodic commit to avoid holding lock too long
        if updated_count % 10 == 0:
            conn.commit()
            
    conn.commit()
    conn.close()
    
    logger.info("\nSummary:")
    logger.info(f"  Updated: {updated_count}")
    logger.info(f"  Skipped: {skipped_count}")
    logger.info("Done!")

if __name__ == "__main__":
    backfill_image_collections()
