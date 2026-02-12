from agent import voice_agent
import uuid
from database import init_db
from booking_service import BookingService
from models import PackageType

def test_package_awareness():
    # 1. Init DB
    init_db()
    
    user_id = f"test_user_pkg_{uuid.uuid4().hex[:6]}"
    session_id_1 = f"test_sess_1_{uuid.uuid4().hex[:6]}"
    
    print(f"\n--- Phase 1: Create a package for user {user_id} ---")
    # Simulate first session to create a package
    BookingService.create_package(session_id_1, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    print("Created 'Maldives Beach Holiday' package.")
    
    # 2. Start a NEW session for the same user
    session_id_2 = f"test_sess_2_{uuid.uuid4().hex[:6]}"
    print(f"\n--- Phase 2: Start new session {session_id_2} for the same user ---")
    print("User: Hi")
    resp = voice_agent.process_message(user_id, session_id_2, "Hi")
    print(f"Agent: {resp}")
    
    if "continue building your maldives beach holiday" in resp.lower():
        print("\n✅ SUCCESS: Agent offered to continue the existing package.")
    else:
        print("\n❌ FAIL: Agent did not recognize the existing package.")

    # 3. Test after adding an item
    print("\n--- Phase 3: Verify item mention exception ---")
    # Fetch package
    pkg = BookingService.get_latest_user_package(user_id)
    from models import PackageItem, BookingStatus
    item = PackageItem(name="Overwater Villa at Soneva Fushi", item_type="hotel", price=1500.0, status=BookingStatus.DRAFT)
    BookingService.add_item_to_package(session_id_2, pkg.id, item)
    print(f"Added item: {item.name}")
    
    print("\nUser: Tell me about my package")
    resp2 = voice_agent.process_message(user_id, session_id_2, "Tell me about my package")
    print(f"Agent: {resp2}")
    
    if "soneva fushi" in resp2.lower() or "overwater villa" in resp2.lower():
        print("\n✅ SUCCESS: Agent mentioned a specific item that IS in the package.")
    else:
        print("\n❌ FAIL: Agent was too secretive about an item ALREADY in the package.")

if __name__ == "__main__":
    test_package_awareness()
