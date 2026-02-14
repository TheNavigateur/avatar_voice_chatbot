import os
import uuid
import logging
from agent import VoiceAgent
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_no_premature_shopping():
    user_id = "test_user_no_shopping"
    session_id = str(uuid.uuid4())
    agent = VoiceAgent()

    # 1. Start planning - Vibe
    logger.info("--- Phase 1: Vibe ---")
    response = agent.process_message(user_id, session_id, "I want to plan a beach holiday.")
    print(f"Agent: {response}")

    # 2. Activity Preference
    logger.info("--- Phase 1: Activity ---")
    response = agent.process_message(user_id, session_id, "I love scuba diving and relaxing.")
    print(f"Agent: {response}")

    # 3. Environment/Dates (Skipping some steps for speed if agent allows)
    logger.info("--- Phase 1: Dates ---")
    response = agent.process_message(user_id, session_id, "I want to go for 7 nights in March 2026.")
    print(f"Agent: {response}")

    # 4. Search & Activity Addition (Moving towards Phase 3)
    # The agent should eventually add an activity.
    # We'll simulate a few more turns to reach the activity adding part.
    
    logger.info("--- Phase 2/3: Activity Planning ---")
    response = agent.process_message(user_id, session_id, "Tell me about some activities.")
    print(f"Agent: {response}")
    
    # We are looking for the LACK of "would you like to see some ... gear/items"
    if "scuba diving gear" in response.lower() or "take with you" in response.lower() or "shopping" in response.lower():
        print("FAIL: Premature shopping offer detected!")
        exit(1)
    else:
        print("SUCCESS: No premature shopping offer found.")

if __name__ == "__main__":
    test_no_premature_shopping()
