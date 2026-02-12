from agent import voice_agent
import uuid

def test_shopping_discovery():
    user_id = f"test_user_shopping_{uuid.uuid4().hex[:6]}"
    session_id = f"test_session_shopping_{uuid.uuid4().hex[:6]}"
    
    # 1. User says they want to plan a shopping trip or just buy something
    print("\nUser: I need to buy some gear for my upcoming hiking trip.")
    resp1 = voice_agent.process_message(user_id, session_id, "I need to buy some gear for my upcoming hiking trip.")
    print(f"Agent: {resp1}")
    
    # 2. Check if agent asks a discriminating question or tries to infer without asking for a brand/model
    # According to the prompt, for complex items, it should search silently and then ask a discriminating question.
    
    if "brand" in resp1.lower() or "model" in resp1.lower() or "which one" in resp1.lower() and "?" in resp1:
        # If it's asking for a specific name, it might be failing the forbidden rule.
        # But asking "Which one" is okay if it's based on features.
        pass

    print("\nUser: I'm looking for hiking boots.")
    resp2 = voice_agent.process_message(user_id, session_id, "I'm looking for hiking boots.")
    print(f"Agent: {resp2}")
    
    # Verify it doesn't just ask "What brand?"
    forbidden_words = ["brand", "name of the", "model", "specific"]
    failed = any(word in resp2.lower() for word in forbidden_words)
    
    if failed:
        print("\n❌ FAIL: Agent asked for a brand or specific name.")
    else:
        print("\n✅ SUCCESS: Agent followed discovery logic.")

if __name__ == "__main__":
    test_shopping_discovery()
