import os
import uuid
import logging
from agent import VoiceAgent
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify():
    user_id = "test_user_shopping"
    session_id = str(uuid.uuid4())
    agent = VoiceAgent()

    # 1. Create a holiday package
    logger.info("Creating a mock holiday package...")
    pkg = BookingService.create_package(session_id, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    
    # 2. Add an item and book it
    item = PackageItem(name="Resort Stay", item_type="hotel", price=1500.0)
    BookingService.add_item_to_package(session_id, pkg.id, item)
    
    # Simulate booking
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
    conn.commit()
    conn.close()
    logger.info(f"Package {pkg.id} marked as BOOKED.")

    # 3. Test Greeting
    logger.info("--- Testing Greeting ---")
    response = agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {response}")
    
    # 4. Accept Shopping Flow
    logger.info("--- Accepting Shopping Flow ---")
    response = agent.process_message(user_id, session_id, "Yes, I'd like to see some beachwear.")
    print(f"Agent: {response}")

    # 5. Simulate sequential response (Yes to first item)
    logger.info("--- Answering Yes to first item ---")
    response = agent.process_message(user_id, session_id, "Yes, I need one.")
    print(f"Agent: {response}")

if __name__ == "__main__":
    verify()
