import sqlite3
from models import PackageType, BookingStatus, PackageItem
from booking_service import BookingService
import uuid

# Create a booked holiday for web_user
user_id = "web_user"
session_id = str(uuid.uuid4())

print(f"Creating booked holiday for {user_id}...")

# Create package
pkg = BookingService.create_package(
    session_id, 
    "Maldives Beach Holiday", 
    PackageType.HOLIDAY, 
    user_id=user_id
)

# Add some items to make it realistic
items = [
    PackageItem(name="Flight to Maldives", item_type="flight", price=450),
    PackageItem(name="Beachfront Resort", item_type="hotel", price=800),
    PackageItem(name="Snorkeling Tour", item_type="activity", price=75)
]

for item in items:
    BookingService.add_item_to_package(session_id, pkg.id, item)

# Mark as booked
conn = sqlite3.connect('app.db')
c = conn.cursor()
c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
conn.commit()
conn.close()

print(f"✅ Created booked holiday: {pkg.title} (ID: {pkg.id})")
print(f"   Status: BOOKED")
print(f"   Items: {len(items)}")
print("\nNow refresh your browser and say 'Hi' to trigger the shopping flow!")
