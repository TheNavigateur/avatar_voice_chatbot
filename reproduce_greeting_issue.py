import os
import sqlite3
import uuid
from agent import voice_agent
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus
from database import init_db

def reproduce():
    # 1. Initialize DB
    init_db()
    
    user_id = "test_user_greeting"
    session_id = str(uuid.uuid4())
    
    print(f"--- Setting up booked holiday for {user_id} ---")
    
    # Clean up existing packages for this test user if any
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("DELETE FROM package_items WHERE package_id IN (SELECT id FROM packages WHERE user_id = ?)", (user_id,))
    c.execute("DELETE FROM packages WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    # Create package
    pkg = BookingService.create_package(
        session_id, 
        "Maldives Beach Holiday", 
        PackageType.HOLIDAY, 
        user_id=user_id
    )
    
    # Add items
    items = [
        PackageItem(name="Flight to Maldives", item_type="flight", price=450),
        PackageItem(name="Beachfront Resort", item_type="hotel", price=800)
    ]
    for item in items:
        BookingService.add_item_to_package(session_id, pkg.id, item)
        
    # Mark as booked
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
    conn.commit()
    conn.close()
    
    print(f"✅ Created booked holiday: {pkg.title}")
    
    # 2. Call agent with "Hi!"
    print("\n--- Sending 'Hi!' to agent ---")
    response = voice_agent.process_message(user_id, session_id, "Hi!")
    
    print("\nAGENT RESPONSE:")
    print("-" * 20)
    print(response)
    print("-" * 20)

if __name__ == "__main__":
    reproduce()
