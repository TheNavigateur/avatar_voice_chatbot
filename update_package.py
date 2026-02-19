import sqlite3
import json

# Connect to database
conn = sqlite3.connect('app.db')
c = conn.cursor()

# Get the latest package
package = c.execute('SELECT id, title FROM packages ORDER BY id DESC LIMIT 1').fetchone()
package_id = package[0]
print(f"Updating package: {package[1]} (ID: {package_id})")

# Get all items
items = c.execute('SELECT id, name, item_type, description FROM package_items WHERE package_id = ? ORDER BY id', (package_id,)).fetchall()

# Update each item with proper metadata
updates = [
    {
        'id': items[0][0],
        'name': 'Travel to Heathrow Airport',
        'item_type': 'activity',
        'description': 'Begin your exciting Paris adventure! Arrive at Heathrow Airport by 9:00 AM for your 11:00 AM departure. Allow extra time for check-in and security.',
        'metadata': json.dumps({'day': 0, 'date': 'Saturday, February 7, 2026'})
    },
    {
        'id': items[0][0],  # First flight - keep as is but update metadata
        'name': items[0][1],
        'item_type': items[0][2],
        'description': items[0][3],
        'metadata': json.dumps({})  # Flights don't need day metadata
    },
    {
        'id': items[1][0],  # Second flight
        'name': items[1][1],
        'item_type': items[1][2],
        'description': items[1][3],
        'metadata': json.dumps({})
    }
]

# Add arrival activity
c.execute('''INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
          ('arrival-transfer-001', package_id, 'Arrival & Transfer to Hotel', 'activity', 0.0, 'draft',
           'Touch down in the City of Light! After landing at 1:00 PM local time, enjoy a scenic transfer to your hotel in the heart of Paris. Check in and freshen up before your Parisian adventure begins.',
           json.dumps({'day': 1, 'date': 'Saturday, February 7, 2026'})))

# Add Day 1 activities
activities_day1 = [
    {
        'id': 'activity-eiffel-001',
        'name': 'Eiffel Tower Experience',
        'description': 'Experience the magic of Paris from above! Ascend the iconic Eiffel Tower and witness breathtaking panoramic views of the city. Watch the sunset paint the Parisian skyline in golden hues as you sip champagne at the summit.',
        'day': 1,
        'date': 'Saturday, February 7, 2026',
        'price': 45.0
    },
    {
        'id': 'activity-seine-001',
        'name': 'Seine River Dinner Cruise',
        'description': 'Indulge in romance and elegance aboard a luxurious Seine River cruise. Savor exquisite French cuisine while gliding past illuminated landmarks including Notre-Dame, the Louvre, and charming Parisian bridges under the stars.',
        'day': 1,
        'date': 'Saturday, February 7, 2026',
        'price': 89.0
    }
]

for activity in activities_day1:
    c.execute('''INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (activity['id'], package_id, activity['name'], 'activity', activity['price'], 'draft',
               activity['description'], json.dumps({'day': activity['day'], 'date': activity['date']})))

# Add Day 2 activities
activities_day2 = [
    {
        'id': 'activity-louvre-001',
        'name': 'Louvre Museum & Mona Lisa',
        'description': 'Discover world-renowned masterpieces at the magnificent Louvre! Skip the lines and explore centuries of art history, from the enigmatic Mona Lisa to the majestic Winged Victory. A cultural journey you\'ll never forget.',
        'day': 2,
        'date': 'Sunday, February 8, 2026',
        'price': 35.0
    },
    {
        'id': 'activity-montmartre-001',
        'name': 'Montmartre & Sacré-Cœur Walking Tour',
        'description': 'Wander through the charming cobblestone streets of Montmartre, where artists and bohemians once thrived. Visit the stunning Sacré-Cœur Basilica, explore hidden squares, and soak in the authentic Parisian atmosphere.',
        'day': 2,
        'date': 'Sunday, February 8, 2026',
        'price': 25.0
    },
    {
        'id': 'activity-patisserie-001',
        'name': 'French Patisserie Workshop',
        'description': 'Unleash your inner pastry chef! Learn the secrets of French baking from a master patissier. Create delicate macarons, flaky croissants, and decadent éclairs, then enjoy your delicious creations with coffee.',
        'day': 2,
        'date': 'Sunday, February 8, 2026',
        'price': 75.0
    }
]

for activity in activities_day2:
    c.execute('''INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (activity['id'], package_id, activity['name'], 'activity', activity['price'], 'draft',
               activity['description'], json.dumps({'day': activity['day'], 'date': activity['date']})))

# Add final day activities
final_activities = [
    {
        'id': 'activity-airport-transfer-001',
        'name': 'Transfer to Charles de Gaulle Airport',
        'description': 'Depart for the airport at 5:00 PM for your 8:00 PM flight. Enjoy one last glimpse of Paris as you travel through the city.',
        'day': 3,
        'date': 'Monday, February 9, 2026',
        'price': 0.0
    },
    {
        'id': 'activity-welcome-home-001',
        'name': 'Welcome Home!',
        'description': '🏡 Congratulations on an unforgettable Parisian adventure! You\'ve experienced the magic, romance, and culture of the City of Light. Until next time, au revoir!',
        'day': 3,
        'date': 'Monday, February 9, 2026',
        'price': 0.0
    }
]

for activity in final_activities:
    c.execute('''INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (activity['id'], package_id, activity['name'], 'activity', activity['price'], 'draft',
               activity['description'], json.dumps({'day': activity['day'], 'date': activity['date']})))

# Update total price
total = c.execute('SELECT SUM(price) FROM package_items WHERE package_id = ?', (package_id,)).fetchone()[0]
c.execute('UPDATE packages SET total_price = ? WHERE id = ?', (total, package_id))

conn.commit()
conn.close()

print(f"✅ Package updated successfully!")
print(f"Added {len(activities_day1) + len(activities_day2) + len(final_activities) + 1} new activities")
print(f"Total package price: £{total}")
