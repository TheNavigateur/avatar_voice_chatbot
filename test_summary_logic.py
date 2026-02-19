import logging
import uuid
from agent import voice_agent
from database import init_db
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_summary_logic():
    init_db()
    user_id = "test_summary_user"
    session_id = str(uuid.uuid4())
    
    # 1. Create a package with items
    print("\n--- Creating package and items ---")
    pkg = BookingService.create_package(session_id, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    package_id = pkg.id
    
    BookingService.add_item_to_package(session_id, package_id, PackageItem(
        name="Luxury Overwater Villa",
        item_type="hotel",
        price=1000.0,
        description="Beautiful villa with ocean view"
    ))
    
    BookingService.add_item_to_package(session_id, package_id, PackageItem(
        name="Sunset Cruise",
        item_type="activity",
        price=200.0,
        description="Romantic cruise at sunset"
    ))
    
    # 2. Test summary request WITH package_id context
    print(f"\n--- Testing summary request for package {package_id} ---")
    msg = "Can you summarise this package for me?"
    resp = voice_agent.process_message(user_id, session_id, msg, package_id=package_id)
    print(f"User: {msg}")
    print(f"Agent: {resp}")
    
    # Verify that the response contains item names and isn't just "on the screen"
    success = "overwater villa" in resp.lower() and "sunset cruise" in resp.lower()
    
    if success:
        print("\n✅ SUCCESS: Agent provided a verbal summary containing items.")
    else:
        print("\n❌ FAIL: Agent did not provide a verbal summary or missed items.")
        if "on the screen" in resp.lower():
            print("  (Agent still saying 'on the screen')")

if __name__ == "__main__":
    test_summary_logic()
