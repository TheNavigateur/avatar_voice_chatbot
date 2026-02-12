from agent import voice_agent
import uuid

def reproduce_discovery_failure():
    user_id = f"test_user_failure_{uuid.uuid4().hex[:6]}"
    session_id = f"test_session_failure_{uuid.uuid4().hex[:6]}"
    
    print("\nUser: Hi")
    resp1 = voice_agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {resp1}")
    
    # Check if resp1 is neutral (not asking about trip vibe)
    if "relaxing" in resp1.lower() or "adventurous" in resp1.lower():
        print("\n❌ FAIL: Agent jumped into trip discovery prematurely.")
    else:
        print("\n✅ SUCCESS: Agent provided a neutral response to 'Hi'.")

    print("\nUser: I want to plan a holiday.")
    resp2 = voice_agent.process_message(user_id, session_id, "I want to plan a holiday.")
    print(f"Agent: {resp2}")
    
    if "relaxing" in resp2.lower() or "adventurous" in resp2.lower():
        print("\n✅ SUCCESS: Agent correctly triggered discovery flow for trip intent.")
    else:
        print("\n❌ FAIL: Agent did not trigger discovery flow for trip intent.")

if __name__ == "__main__":
    reproduce_discovery_failure()
