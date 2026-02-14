import os
import logging
import uuid
from agent import voice_agent
from booking_service import BookingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reproduce_package_navigation():
    user_id = "test_user_" + str(uuid.uuid4())[:8]
    session_id = "test_session_" + str(uuid.uuid4())[:8]
    
    print(f"Session ID: {session_id}")
    
    # Simulate a conversation that leads to package creation and reveal
    messages = [
        "Plan a relaxing beach holiday for me",
        "I like surfing and cocktails",
        "Around March 25th for 5 nights",
        "2 travelers",
        "A boutique hideaway please",
        "Make it active with some surfing",
        "Can you finalize it now?"
    ]
    
    for msg in messages:
        print(f"\nUser: {msg}")
        response = voice_agent.process_message(user_id, session_id, msg)
        print(f"Agent: {response}")
        
        if "[NAVIGATE_TO_PACKAGE]" in response:
            print("\nFound [NAVIGATE_TO_PACKAGE] marker!")
            
            # Check if package exists for this session
            packages = BookingService.get_packages(session_id)
            print(f"Packages found for session: {len(packages)}")
            for p in packages:
                print(f" - Package: {p.title} (ID: {p.id}), Items: {len(p.items)}")
                for item in p.items:
                    print(f"   * {item.item_type}: {item.name}")
            
            if not packages:
                print("\n❌ FAILURE: [NAVIGATE_TO_PACKAGE] sent but no packages found in DB for this session.")
            else:
                print("\n✅ SUCCESS: Package found in DB.")
            return

    print("\n⚠️ Finished conversation without [NAVIGATE_TO_PACKAGE]. Check agent instructions.")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        reproduce_package_navigation()
