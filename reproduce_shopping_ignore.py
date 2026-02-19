import os
import uuid
import logging
from agent import VoiceAgent
from booking_service import BookingService
from profile_service import ProfileService
from models import PackageType, PackageItem, BookingStatus
from database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reproduce():
    user_id = f"repro_user_{uuid.uuid4().hex[:6]}"
    session_id = str(uuid.uuid4())
    agent = VoiceAgent()

    # 1. Create and book a holiday
    pkg = BookingService.create_package(session_id, "Ibiza Party Holiday", PackageType.HOLIDAY, user_id=user_id)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
    conn.commit()
    conn.close()

    # 2. Start conversation and get to the first shopping question
    logger.info("--- Step 1: Greeting ---")
    res1 = agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {res1}")

    logger.info("--- Step 2: Accept Shopping ---")
    res2 = agent.process_message(user_id, session_id, "Yes, I need to shop for my Ibiza trip.")
    print(f"Agent: {res2}")

    # If it showed the checklist, we need to say "Continue"
    if "[SHOPPING_CHECKLIST]" in res2:
        logger.info("--- Step 3: Simulate UI Update (I have sun cream) ---")
        ProfileService.append_to_profile(user_id, "I have sun cream")
        
        logger.info("--- Step 3b: Continue from Checklist ---")
        res3 = agent.process_message(user_id, session_id, "Continue")
        print(f"Agent: {res3}")
        
        profile = ProfileService.get_profile(user_id)
        logger.info(f"Profile after Continue:\n{profile}")
    else:
        res3 = res2


    # Now we should be at a discovery question for an item (e.g., Sun Cream)
    logger.info("--- Step 4: Say 'I already have it' ---")
    res4 = agent.process_message(user_id, session_id, "Actually I already have sun cream.")
    print(f"Agent: {res4}")

    # The expected behavior: Agent should move to the NEXT item or acknowledge it's skipped.
    # The reported behavior: Agent repeats question or asks for details anyway.

if __name__ == "__main__":
    reproduce()
