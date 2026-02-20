from agent import voice_agent
import uuid
from database import init_db
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus
import json

def reproduce_issue():
    # 1. Init DB
    init_db()
    
    user_id = f"test_user_planned_{uuid.uuid4().hex[:6]}"
    session_id = f"test_sess_{uuid.uuid4().hex[:6]}"
    
    print(f"\n--- Setting up data for user {user_id} ---")
    
    # Create several draft packages
    for i in range(4):
        pkg = BookingService.create_package(session_id, f"Maldives Beach Holiday Draft {i+1}", PackageType.HOLIDAY, user_id=user_id)
        print(f"Created draft package: {pkg.title}")
        
    # Create one booked package
    booked_pkg = BookingService.create_package(session_id, "Maldives Beach Holiday Booked", PackageType.HOLIDAY, user_id=user_id)
    # Simulate booking
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, booked_pkg.id))
    conn.commit()
    conn.close()
    print(f"Created booked package: {booked_pkg.title}")
    
    print(f"\n--- Step 1: Ask the general question ---")
    print(f"User: can you tell me what you have planned for me")
    resp1 = voice_agent.process_message(user_id, session_id, "can you tell me what you have planned for me")
    print(f"Agent: {resp1}")
    
    # Check if agent claimed to have nothing planned
    nothing_planned_keywords = ["don't have anything planned", "no packages", "nothing planned yet", "nothing saved"]
    shoud_fail_check = any(keyword in resp1.lower() for keyword in nothing_planned_keywords)
    
    if shoud_fail_check:
        print("\n❌ REPRODUCED: Agent claimed it has nothing planned despite existing packages.")
    else:
        print("\n✅ SUCCESS (or partial): Agent acknowledged packages in response.")

    print(f"\n--- Step 2: Ask the specific question ---")
    print(f"User: is there a Maldives beach holiday package we have planned")
    resp2 = voice_agent.process_message(user_id, session_id, "is there a Maldives beach holiday package we have planned")
    print(f"Agent: {resp2}")
    
    if "maldives" in resp2.lower() and ("several" in resp2.lower() or "draft" in resp2.lower() or "booked" in resp2.lower()):
        print("\n✅ CONFIRMED: Agent correctly identifies packages when asked specifically.")
    else:
        print("\n❌ STILL FAILING: Agent failed to identify packages even with a specific query.")

if __name__ == "__main__":
    reproduce_issue()
