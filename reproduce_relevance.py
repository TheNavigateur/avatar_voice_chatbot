import os
os.environ["DB_NAME"] = "test_relevance.db"

import sqlite3
import uuid
from agent import VoiceAgent
from models import PackageType, BookingStatus
from database import init_db

# Use a test database
if os.path.exists("test_relevance.db"):
    os.remove("test_relevance.db")

init_db()

def setup_data(user_id, session_id):
    conn = sqlite3.connect("test_relevance.db")
    c = conn.cursor()
    
    # Create a booked holiday
    pkg_id = str(uuid.uuid4())
    c.execute("""
        INSERT INTO packages (id, session_id, user_id, title, type, status, total_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (pkg_id, session_id, user_id, "Maldives Holiday", PackageType.HOLIDAY.value, BookingStatus.BOOKED.value, 1500.0))
    
    # Add an item to the holiday
    c.execute("""
        INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (str(uuid.uuid4()), pkg_id, "Beach Resort", "hotel", 1500.0, BookingStatus.BOOKED.value, "Luxury resort", "{}"))
    
    conn.commit()
    conn.close()

def main():
    agent = VoiceAgent()
    user_id = "test_user_123"
    session_id = "test_session_456"
    
    setup_data(user_id, session_id)
    
    # First message: Greet or ask about history
    query = "what holidays have we looked at"
    print(f"User: {query}")
    
    response = agent.process_message(user_id, session_id, query)
    print(f"Bot: {response}")

    # Check if the bot answered the question or jumped to shopping
    if "Maldives" in response and ("shopping" in response.lower() or "items" in response.lower()):
        print("\nISSUE REPRODUCED: Bot jumped to shopping checklist instead of answering the question.")
    else:
        print("\nISSUE NOT REPRODUCED or bot answered correctly.")

if __name__ == "__main__":
    main()
