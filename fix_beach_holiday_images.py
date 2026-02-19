#!/usr/bin/env python3
"""Fix all activities in Beach Holiday package with reliable images"""
import sys, os, subprocess, sqlite3, json

# Load env
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd='/Users/naveenchawla/Repos/google_adk_voice_bot')
for line in result.stdout.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value

sys.path.insert(0, '/Users/naveenchawla/Repos/google_adk_voice_bot')
from services.image_search_service import ImageSearchService

conn = sqlite3.connect('app.db')
c = conn.cursor()

service = ImageSearchService()

# Get Beach Holiday package with 4 items
package = c.execute('''
    SELECT p.id, p.title
    FROM packages p
    LEFT JOIN package_items pi ON p.id = pi.package_id
    WHERE p.title LIKE '%Beach Holiday%'
    GROUP BY p.id
    HAVING COUNT(pi.id) = 4
''').fetchone()

if not package:
    print("❌ Package not found")
    exit(1)

package_id, package_title = package
print(f"📦 Fixing: {package_title}\n")

# Get all activities
activities = c.execute('''
    SELECT id, name, metadata
    FROM package_items
    WHERE package_id = ? AND item_type = 'activity'
''', (package_id,)).fetchall()

for item_id, name, metadata_str in activities:
    metadata = json.loads(metadata_str) if metadata_str else {}
    current_image = metadata.get('image_url', '')
    
    print(f"🔍 {name}")
    print(f"   Current: {current_image[:60]}...")
    
    # Check if it's a problematic URL
    if any(domain in current_image for domain in ['getyourguide.com', 'tripadvisor.com', 'unsplash.com']):
        print(f"   ⚠️  Unreliable source, searching for better image...")
        
        # Search for a reliable image
        new_image = service.get_activity_image(name, 'Tenerife')
        
        if new_image and 'wikimedia' in new_image.lower():
            metadata['image_url'] = new_image
            c.execute('UPDATE package_items SET metadata = ? WHERE id = ?', (json.dumps(metadata), item_id))
            print(f"   ✅ Updated with Wikimedia image")
            print(f"   New: {new_image[:60]}...")
        elif new_image:
            metadata['image_url'] = new_image
            c.execute('UPDATE package_items SET metadata = ? WHERE id = ?', (json.dumps(metadata), item_id))
            print(f"   ✅ Updated with Pixabay image")
            print(f"   New: {new_image[:60]}...")
        else:
            print(f"   ❌ No better image found")
    else:
        print(f"   ✓ Already has reliable image")
    
    print()

conn.commit()
conn.close()

print("🎉 Done!")
