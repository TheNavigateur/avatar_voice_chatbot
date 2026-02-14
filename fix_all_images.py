#!/usr/bin/env python3
import os
import sys
import sqlite3
import json
import logging
import subprocess

# Add current directory to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd=os.getcwd())
for line in result.stdout.split('\n'):
    if '=' in line:
        parts = line.split('=', 1)
        if len(parts) == 2:
            key, value = parts
            os.environ[key] = value

from services.image_search_service import ImageSearchService

def fix_all_images():
    service = ImageSearchService()
    db_path = 'app.db'
    
    if not os.path.exists(db_path):
        logger.error(f"Database {db_path} not found")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Domains we consider unreliable or likely to fail
    unreliable_domains = ['getyourguide.com', 'tripadvisor.com', 'viator.com', 'booking.com']
    
    # Patterns that indicate a "bad" image
    bad_patterns = [
        '.pdf', '.svg', 'ia_sunrise', 'ebbflow', 'book cover', 
        'geograph.org.uk', 'larne', 'placeholder', 'no-image'
    ]
    
    cursor.execute("SELECT id, name, item_type, metadata FROM package_items")
    items = cursor.fetchall()
    
    logger.info(f"Checking {len(items)} items...")
    
    fixed_count = 0
    skipped_count = 0
    
    for item in items:
        item_id = item['id']
        name = item['name']
        item_type = item['item_type']
        metadata_str = item['metadata']
        
        metadata = json.loads(metadata_str) if metadata_str else {}
        old_url = metadata.get('image_url', '')
        
        needs_fix = False
        reason = ""
        
        if not old_url:
            needs_fix = True
            reason = "Missing URL"
        elif any(domain in old_url.lower() for domain in unreliable_domains):
            needs_fix = True
            reason = f"Unreliable domain: {next(d for d in unreliable_domains if d in old_url.lower())}"
        elif any(pattern in old_url.lower() for pattern in bad_patterns):
            needs_fix = True
            reason = f"Bad pattern: {next(p for p in bad_patterns if p in old_url.lower())}"
        elif 'station' in old_url.lower() and 'arrival' in name.lower():
            needs_fix = True
            reason = "Generic station image for 'Arrival'"
            
        if needs_fix:
            logger.info(f"🔧 Fixing '{name}' ({item_type}) - Reason: {reason}")
            
            new_url = None
            if item_type == 'hotel':
                res = service.get_hotel_image(name)
                new_url = res[0] if res and isinstance(res, list) else res
            elif item_type == 'activity':
                # Get package title for location context if possible
                cursor.execute("SELECT title FROM packages p JOIN package_items pi ON p.id = pi.package_id WHERE pi.id = ?", (item_id,))
                pkg_row = cursor.fetchone()
                location = None
                if pkg_row:
                    location = pkg_row['title'].replace('Holiday', '').replace('Trip', '').replace('Getaway', '').strip()
                res = service.get_activity_image(name, location)
                new_url = res[0] if res and isinstance(res, list) else res
            elif item_type == 'flight':
                res = service.get_flight_image(name)
                new_url = res[0] if res and isinstance(res, list) else res
            else:
                new_url = service.search_image(name)
                
            if new_url and new_url != old_url:
                logger.info(f"  ✅ Updated: {new_url[:70]}...")
                metadata['image_url'] = new_url
                cursor.execute("UPDATE package_items SET metadata = ? WHERE id = ?", (json.dumps(metadata), item_id))
                fixed_count += 1
            else:
                logger.warning(f"  ❌ Could not find a better image for: {name}. REMOVING bad image.")
                if 'image_url' in metadata:
                    del metadata['image_url']
                cursor.execute("UPDATE package_items SET metadata = ? WHERE id = ?", (json.dumps(metadata), item_id))
                fixed_count += 1
        else:
            skipped_count += 1
            
    conn.commit()
    conn.close()
    
    logger.info("\nSummary:")
    logger.info(f"  Fixed: {fixed_count}")
    logger.info(f"  Kept/Skipped: {skipped_count}")
    logger.info("Done!")

if __name__ == "__main__":
    fix_all_images()
