from agent import voice_agent
import uuid

def reproduce_discovery_failure():
    user_id = f"test_user_failure_{uuid.uuid4().hex[:6]}"
    session_id = f"test_session_failure_{uuid.uuid4().hex[:6]}"
    
    print("\nUser: Hi")
    resp1 = voice_agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {resp1}")
    
    print("\nUser: yeah I'd like a beach holiday I'd like 28 degrees average day temperature please")
    resp2 = voice_agent.process_message(user_id, session_id, "yeah I'd like a beach holiday I'd like 28 degrees average day temperature please")
    print(f"Agent: {resp2}")
    
    # Check if the response contains anything related to asking for a destination name
    if "where" in resp2.lower() and ("going" in resp2.lower() or "destination" in resp2.lower() or "place" in resp2.lower()):
        print("\n❌ REPRODUCED: Agent asked for a destination.")
    else:
        print("\n✅ COULD NOT REPRODUCE: Agent followed discovery logic.")

if __name__ == "__main__":
    reproduce_discovery_failure()
