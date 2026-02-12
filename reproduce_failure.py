from agent import voice_agent
import uuid
from database import init_db

def reproduce_discovery_failure():
    # Initialize database for migrations
    init_db()
    
    user_id = f"test_user_failure_{uuid.uuid4().hex[:6]}"
    session_id = f"test_session_failure_{uuid.uuid4().hex[:6]}"
    
    print("\nUser: Hi")
    resp1 = voice_agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {resp1}")
    
    # Check if resp1 starts with "Hi! I'm Ray."
    if "i'm ray" in resp1.lower() and "thinking about a holiday" in resp1.lower():
        print("\n✅ SUCCESS: Agent introduced itself and asked about a holiday (New User).")
    else:
        print("\n❌ FAIL: Agent greeting was not correct for a new user.")

    # Test returning user with profile
    user_id_profile = f"test_user_profile_{uuid.uuid4().hex[:6]}"
    from profile_service import ProfileService
    ProfileService.update_profile(user_id_profile, "User loves Italian food, history, and quiet boutique hotels. They enjoy visiting museums and ancient ruins.")
    
    print(f"\nUser (with context): Hi")
    resp3 = voice_agent.process_message(user_id_profile, str(uuid.uuid4()), "Hi")
    print(f"Agent: {resp3}")
    
    # Check for contextual keywords but FORBID location/assumption keywords
    contains_experience = any(word in resp3.lower() for word in ["food", "history", "museum", "ancient", "boutique"])
    contains_location = any(word in resp3.lower() for word in ["italy", "maldives", "rome", "athens"])
    contains_assumption = any(word in resp3.lower() for word in ["another", "again", "returning", "back to"])
    
    if "i'm ray" in resp3.lower() and contains_experience and not contains_location and not contains_assumption:
        print("\n✅ SUCCESS: Agent provided a contextual greeting based on EXPERIENCE, not location.")
    elif contains_location:
        print("\n❌ FAIL: Agent mentioned a location (e.g., 'Italy') in the greeting.")
    elif contains_assumption:
        print("\n❌ FAIL: Agent assumed past history.")
    else:
        print("\n❌ FAIL: Agent did not provide a correct contextual greeting.")

if __name__ == "__main__":
    reproduce_discovery_failure()
