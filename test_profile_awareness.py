from agent import voice_agent
import uuid
from database import init_db
from profile_service import ProfileService

def test_profile_awareness():
    # 1. Init DB
    init_db()
    
    user_id = f"test_user_profile_{uuid.uuid4().hex[:6]}"
    session_id = f"test_sess_{uuid.uuid4().hex[:6]}"
    
    print(f"\n--- Setting up profile for user {user_id} ---")
    
    profile_content = "The user is from London. They love Maldives beach holidays and prefer luxury resorts. They are vegan."
    ProfileService.update_profile(user_id, profile_content)
    print(f"Profile set: {profile_content}")
    
    print(f"\n--- Step 1: Ask the agent what it knows ---")
    print(f"User: what do you know about my preferences?")
    resp1 = voice_agent.process_message(user_id, session_id, "what do you know about my preferences?")
    print(f"Agent: {resp1}")
    
    # Check if agent knows about the profile without tool call
    knows_location = "london" in resp1.lower()
    knows_preference = "maldives" in resp1.lower() or "beach" in resp1.lower()
    knows_diet = "vegan" in resp1.lower()
    
    if knows_location and knows_preference and knows_diet:
        print("\n✅ SUCCESS: Agent is aware of the user's profile context.")
    else:
        print("\n❌ FAIL: Agent missed some profile information.")

if __name__ == "__main__":
    test_profile_awareness()
