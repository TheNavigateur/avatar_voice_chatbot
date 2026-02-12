from agent import voice_agent
import uuid

def reproduce_discovery_failure():
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
    
    if "i'm ray" in resp3.lower() and ("italy" in resp3.lower() or "history" in resp3.lower() or "museum" in resp3.lower() or "ancient" in resp3.lower() or "boutique" in resp3.lower()):
        print("\n✅ SUCCESS: Agent provided a contextual greeting based on profile.")
    else:
        print("\n❌ FAIL: Agent did not provide a contextual greeting.")

if __name__ == "__main__":
    reproduce_discovery_failure()
