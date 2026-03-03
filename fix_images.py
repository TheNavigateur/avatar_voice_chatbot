import os
import json
import logging
from database import get_db_connection
from booking_service import BookingService
from agent import _enrich_item_metadata
from models import PackageItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_existing_packages():
    conn = get_db_connection()
    c = conn.cursor()
    # Let's fix the most recent 10 packages to start with
    c.execute("SELECT * FROM packages ORDER BY rowid DESC LIMIT 10")
    packages = c.fetchall()
    
    for pkg_row in packages:
        pkg_id = pkg_row['id']
        session_id = pkg_row['session_id']
        logger.info(f"Processing package: {pkg_row['title']} ({pkg_id})")
        
        # Get items for this package
        c.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg_id,))
        item_rows = c.fetchall()
        
        for item_data in item_rows:
            try:
                meta = json.loads(item_data['metadata']) if item_data['metadata'] else {}
            except Exception as e:
                meta = {}
            
            existing_images = meta.get('images', [])
            item_type = item_data['item_type']
            item_name = item_data['name']
            
            # Check if this item is missing images or has less than 3
            if item_type in ['flight', 'hotel', 'accommodation', 'activity', 'product']:
                if not existing_images or len(existing_images) < 3:
                    logger.info(f"  -> Enriching '{item_name}' (type: {item_type}) with more images...")
                    
                    # Construct a temporary PackageItem object
                    pkg_item = PackageItem(
                        id=item_data['id'],
                        name=item_name,
                        item_type=item_type,
                        price=item_data['price'],
                        description=item_data['description'],
                    )
                    pkg_item.metadata = meta # carry over existing metadata
                    
                    # Call our shared helper to fetch images (and validate)
                    updated_item = _enrich_item_metadata(
                        session_id=session_id,
                        package_id=pkg_id,
                        item=pkg_item,
                        item_name=item_name,
                        item_type=item_type,
                        image_url=meta.get('image_url'),
                        images=existing_images
                    )
                    
                    # Store back to DB
                    c2 = conn.cursor()
                    c2.execute("UPDATE package_items SET metadata = ? WHERE id = ?", (json.dumps(updated_item.metadata), item_data['id']))
                    conn.commit()
                else:
                    logger.info(f"  -> '{item_name}' already has {len(existing_images)} images. Skipping.")
            
    conn.close()
    logger.info("Done fixing existing packages.")

if __name__ == '__main__':
    fix_existing_packages()
