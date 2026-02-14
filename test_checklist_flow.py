import os
import uuid
import logging
import json
from agent import VoiceAgent
from booking_service import BookingService
from profile_service import ProfileService
from models import PackageType, BookingStatus
from database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_checklist():
    user_id = f"test_checklist_user_{uuid.uuid4().hex[:6]}"
    session_id = str(uuid.uuid4())
    agent = VoiceAgent()

    # 1. Setup profile with some pre-existing facts
    logger.info(f"Setting up profile for {user_id}...")
    ProfileService.update_profile(user_id, "# About Me\n- I have mens swimwear\n- I don't want a sarong")

    # 2. Create and book a holiday to trigger shopping flow
    logger.info("Creating booked holiday...")
    pkg = BookingService.create_package(session_id, "Bali Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
    conn.commit()
    conn.close()

    # 3. Start conversation
    logger.info("--- Greeting ---")
    res1 = agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {res1}")

    # 4. Accept shopping
    logger.info("--- Accepting Shopping ---")
    res2 = agent.process_message(user_id, session_id, "Yes, show me items for my Bali trip.")
    print(f"Agent response contains [SHOPPING_CHECKLIST]: {'[SHOPPING_CHECKLIST]' in res2}")
    
    if '[SHOPPING_CHECKLIST]' in res2:
        # Extract and verify pre-population
        import re
        match = re.search(r'\[SHOPPING_CHECKLIST\]([\s\S]*?)\[\/SHOPPING_CHECKLIST\]', res2)
        if match:
            content = json.loads(match.group(1))
            items = content.get('items', [])
            logger.info("Verifying pre-population...")
            for item in items:
                if "swimwear" in item['name'].lower():
                    logger.info(f"Found {item['name']}: status={item['status']} (Expected: have)")
                if "sarong" in item['name'].lower():
                    logger.info(f"Found {item['name']}: status={item['status']} (Expected: dont_want)")

    # 5. Simulate sizes
    logger.info("--- Providing Sizes ---")
    res3 = agent.process_message(user_id, session_id, "I'm a size XL for swimwear.")
    print(f"Agent: {res3}")
    
    # 6. Verify profile update
    profile = ProfileService.get_profile(user_id)
    logger.info(f"Final Profile content:\n{profile}")

if __name__ == "__main__":
    verify_checklist()
