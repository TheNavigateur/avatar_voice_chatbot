"""
Simulation of the shopping flow fail case.
"""
from agent import VoiceAgent
import logging

# Configure logging to see tool calls
logging.basicConfig(level=logging.INFO)

def simulate_shopping_flow():
    agent = VoiceAgent()
    user_id = "web_user"
    session_id = "test_simulation_session"
    
    # 0. User says "Hi" to see if shopping offer is made
    print("\n--- STEP 0: Greeting ---")
    res0 = agent.process_message(user_id, session_id, "Hi")
    print(f"Agent: {res0}")
    
    # 1. User says "Yes" to shopping
    print("\n--- STEP 1: Acceptance ---")
    res1 = agent.process_message(user_id, session_id, "Yes, I'd like to see recommended items.")
    print(f"Agent: {res1}")
    
    # 3. User provides all info for first item
    print("\n--- STEP 3: Complete First Item ---")
    res3 = agent.process_message(user_id, session_id, "I'm a size Large, I like blue, cotton, budget under £30, and I like Adidas.")
    print(f"Agent: {res3}")
    
    # 4. Check if tools were called
    print("\n--- STEP 4: Verification ---")
    # We check if any items were added to DB or if agent reported tool execution

if __name__ == "__main__":
    simulate_shopping_flow()
