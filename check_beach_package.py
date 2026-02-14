import sqlite3
import json

conn = sqlite3.connect('app.db')
c = conn.cursor()

# Find the Beach Holiday package with 4 items
packages = c.execute('''
    SELECT p.id, p.title, COUNT(pi.id) as item_count
    FROM packages p
    LEFT JOIN package_items pi ON p.id = pi.package_id
    WHERE p.title LIKE '%Beach Holiday%'
    GROUP BY p.id
    HAVING item_count = 4
''').fetchall()

print("Beach Holiday packages with 4 items:")
for pkg_id, title, count in packages:
    print(f"\nPackage: {title} (ID: {pkg_id})")
    
    items = c.execute('''
        SELECT id, name, item_type, metadata
        FROM package_items
        WHERE package_id = ?
    ''', (pkg_id,)).fetchall()
    
    for item_id, name, item_type, metadata_str in items:
        metadata = json.loads(metadata_str) if metadata_str else {}
        image_url = metadata.get('image_url', 'NO IMAGE')
        rating = metadata.get('rating', 'NO RATING')
        
        print(f"  - {name} ({item_type})")
        print(f"    Image: {image_url}")
        print(f"    Rating: {rating}")

conn.close()
