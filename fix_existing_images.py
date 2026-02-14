
import os
import sys
import sqlite3
import json
import logging

# Add current directory to path
sys.path.append(os.getcwd())

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
import subprocess
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd=os.getcwd())
for line in result.stdout.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value

from services.image_search_service import ImageSearchService

def fix_images():
    service = ImageSearchService()
    db_path = 'app.db'
    
    if not os.path.exists(db_path):
        logger.error(f"Database {db_path} not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Query for items with bad images or Sunrise Stay
    query = """
    SELECT id, name, item_type, metadata 
    FROM package_items 
    WHERE metadata LIKE '%.pdf%' 
       OR metadata LIKE '%ia_sunrise%' 
       OR metadata LIKE '%ebbflow%' 
       OR name LIKE '%Sunrise Stay%';
    """
    
    cursor.execute(query)
    items = cursor.fetchall()
    
    if not items:
        logger.info("No items found that need fixing")
        return

    logger.info(f"Found {len(items)} items to fix")
    
    for item_id, name, item_type, metadata_str in items:
        logger.info(f"Fixing item: {name} ({item_type}, ID: {item_id})")
        
        metadata = json.loads(metadata_str)
        old_url = metadata.get('image_url')
        logger.info(f"  Old URL: {old_url}")
        
        new_url = None
        if item_type == 'hotel':
            new_url = service.get_hotel_image(name)
        elif item_type == 'activity':
            new_url = service.get_activity_image(name)
        elif item_type == 'flight':
            new_url = service.get_flight_image(name)
        else:
            new_url = service.search_image(name)
            
        if new_url and new_url != old_url:
            logger.info(f"  New URL: {new_url}")
            metadata['image_url'] = new_url
            
            update_query = "UPDATE package_items SET metadata = ? WHERE id = ?"
            cursor.execute(update_query, (json.dumps(metadata), item_id))
            logger.info(f"  Updated database for item: {name}")
        elif new_url == old_url:
            logger.info(f"  No change in URL for: {name}")
        else:
            logger.warning(f"  Could not find a new image for: {name}")
            
    conn.commit()
    conn.close()
    logger.info("Finished fixing images")

if __name__ == "__main__":
    fix_images()
