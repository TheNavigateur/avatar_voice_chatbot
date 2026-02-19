from agent import VoiceAgent
from booking_service import BookingService
from models import PackageItem, PackageType
import uuid
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_agent_removal():
    agent = VoiceAgent()
    user_id = f"test_user_{uuid.uuid4()}"
    session_id = f"test_session_{uuid.uuid4()}"
    
    # 1. Create a package and add an item
    logger.info("Setting up package for agent test...")
    pkg = BookingService.create_package(session_id, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    item = PackageItem(name="Sunscreen SPF 50", item_type="product", price=15.0)
    item_id = item.id
    BookingService.add_item_to_package(session_id, pkg.id, item)
    
    logger.info(f"Package {pkg.id} created with item {item.name} ({item_id})")
    
    # 2. Ask the agent to remove the item
    message = f"I've changed my mind about the Sunscreen (ID: {item_id}). Can you remove it from my Maldives Beach Holiday package?"
    
    logger.info(f"Sending message to agent: {message}")
    response = agent.process_message(user_id, session_id, message)
    
    logger.info(f"Agent Response: {response}")
    
    # 3. Verify item is removed from DB
    updated_pkg = BookingService.get_package(session_id, pkg.id)
    logger.info(f"Items in package: {[i.name for i in updated_pkg.items]}")
    
    if len(updated_pkg.items) == 0:
        logger.info("SUCCESS: Agent removed the item.")
    else:
        logger.error("FAILURE: Item still in package.")

if __name__ == "__main__":
    verify_agent_removal()
