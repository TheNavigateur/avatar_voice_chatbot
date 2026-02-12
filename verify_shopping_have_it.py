import os
import uuid
import logging
from agent import VoiceAgent
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus
from database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_have_it():
    user_id = f"test_user_have_it_{uuid.uuid4().hex[:6]}"
    session_id = str(uuid.uuid4())
    agent = VoiceAgent()

    # 1. Create and book a holiday
    logger.info(f"Creating and booking a holiday for {user_id}...")
    pkg = BookingService.create_package(session_id, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
    conn.commit()
    conn.close()
    
    # 2. Start conversation
    logger.info("--- Greeting ---")
    res1 = agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {res1}")
    
    # 3. Accept Shopping
    if "booked" in res1.lower():
        logger.info("--- Accepting Shopping ---")
        res2 = agent.process_message(user_id, session_id, "Yes, that would be great.")
        print(f"Agent: {res2}")
        
        # 4. Say "I have it"
        logger.info("--- Saying I have it ---")
        res3 = agent.process_message(user_id, session_id, "I already have one of those.")
        print(f"Agent: {res3}")
        
        # 5. Say "Yes" to next item
        logger.info("--- Saying Yes to next item ---")
        res4 = agent.process_message(user_id, session_id, "Yes, show me one.")
        print(f"Agent: {res4}")
    else:
        logger.error("Agent did not suggest shopping flow in greeting.")

if __name__ == "__main__":
    verify_have_it()
