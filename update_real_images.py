#!/usr/bin/env python3
"""
Update existing packages with real images from web search
"""
import sqlite3
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, '/Users/naveenchawla/Repos/google_adk_voice_bot')

# Load environment variables
import subprocess
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd='/Users/naveenchawla/Repos/google_adk_voice_bot')
for line in result.stdout.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value

from services.image_search_service import ImageSearchService

def update_package_images():
    """Update all activities with real images from web search"""
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    image_service = ImageSearchService()
    
    # Get all packages
    packages = c.execute('SELECT id, title FROM packages').fetchall()
    
    print(f"Updating images for {len(packages)} packages...\n")
    
    total_updated = 0
    
    for package_id, package_title in packages:
        print(f"📦 {package_title}")
        
        # Extract location from package title
        location = package_title.replace('Holiday', '').replace('Trip', '').replace('Getaway', '').replace('Package', '').strip()
        
        # Get all activities in this package
        activities = c.execute('''
            SELECT id, name, metadata
            FROM package_items
            WHERE package_id = ? AND item_type = 'activity'
        ''', (package_id,)).fetchall()
        
        for item_id, name, metadata_str in activities:
            metadata = json.loads(metadata_str) if metadata_str else {}
            
            # Skip if already has a good image (not a fallback)
            current_image = metadata.get('image_url', '')
            if current_image and 'unsplash.com' not in current_image:
                print(f"  ✓ {name} - already has image")
                continue
            
            # Skip airport/transfer activities
            if any(word in name.lower() for word in ['airport', 'transfer', 'welcome home', 'travel to']):
                print(f"  ⊘ {name} - skipping (transfer/airport)")
                continue
            
            print(f"  🔍 Searching for: {name}")
            
            # Search for image
            image_url = image_service.get_activity_image(name, location)
            
            if image_url:
                metadata['image_url'] = image_url
                
                c.execute('''
                    UPDATE package_items
                    SET metadata = ?
                    WHERE id = ?
                ''', (json.dumps(metadata), item_id))
                
                print(f"    ✅ Updated with real image")
                total_updated += 1
            else:
                print(f"    ❌ No image found")
        
        print()
    
    conn.commit()
    conn.close()
    
    print(f"\n🎉 Updated {total_updated} activities with real images!")

if __name__ == '__main__':
    update_package_images()
