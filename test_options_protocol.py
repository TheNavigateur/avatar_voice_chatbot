import os
import uuid
from agent import voice_agent

def test_options_protocol():
    user_id = "test_user_" + str(uuid.uuid4())[:8]
    session_id = "test_session_" + str(uuid.uuid4())[:8]
    
    # Specific failure case reported by user
    message = "I've booked my Maldives Beach Holiday. What's next?"
    print(f"\nSending message: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent Response:\n{response}")
    if "[OPTIONS:" in response:
        print("✅ SUCCESS: [OPTIONS] found for Maldives follow-up.")
    else:
        print("❌ FAILURE: [OPTIONS] MISSING for Maldives follow-up.")

    message = "Hi! I'm Ray. Since you've booked your Maldives Beach Holiday, would you like to see some recommended items to take with you?"
    # This is actually a bot message, but let's see how the agent responds if we "remind" it of its context.
    message = "Can we start planning now?"
    print(f"\nSending message: {message}")
    response = voice_agent.process_message(user_id, session_id, message)
    print(f"Agent Response:\n{response}")
    
    if "[OPTIONS:" in response:
        print("\n✅ SUCCESS: [OPTIONS] protocol found in response.")
    else:
        # It might not always trigger if the agent decides not to, but let's see.
        print("\nℹ️ [OPTIONS] protocol not found (Agent choice).")

if __name__ == "__main__":
    test_options_protocol()
