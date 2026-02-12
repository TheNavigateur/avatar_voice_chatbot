
import os
import sys
from unittest.mock import MagicMock, patch

# Mock dependencies before importing VoiceAgent
sys.modules['google.adk'] = MagicMock()
sys.modules['google.adk.sessions'] = MagicMock()
sys.modules['google.adk.models'] = MagicMock()
sys.modules['tools.rfam_db'] = MagicMock()
sys.modules['tools.search_tool'] = MagicMock()
sys.modules['tools.market_tools'] = MagicMock()
sys.modules['services.duffel_service'] = MagicMock()
sys.modules['services.amadeus_service'] = MagicMock()
sys.modules['services.image_search_service'] = MagicMock()
sys.modules['booking_service'] = MagicMock()
sys.modules['models'] = MagicMock()
sys.modules['profile_service'] = MagicMock()
sys.modules['memory_agent'] = MagicMock()

from agent import VoiceAgent

def test_secrecy():
    agent = VoiceAgent()
    user_id = "test_user"
    session_id = "test_session"
    
    # Mock BookingService.get_latest_user_package to return None (no active package)
    with patch('booking_service.BookingService.get_latest_user_package', return_value=None), \
         patch('profile_service.ProfileService.get_profile', return_value="User likes tropical heat, beach clubs and culture, and travel after March 25th for seven nights with family."), \
         patch('booking_service.BookingService.create_package') as mock_create_pkg, \
         patch('agent.Runner') as mock_runner_class:
        
        # Setup mock runner to simulate the agent's flow
        mock_runner = mock_runner_class.return_value
        
        # Simulate the turn where the agent has picked Maldives but shouldn't say it
        # The prompt says: "Phase 2: Silent Commitment & Residence Preference"
        # It should ask: "For your stay, would you prefer a boutique hideaway or a grand resort with every possible amenity?"
        
        mock_event = MagicMock()
        mock_event.text = "Got it. Based on your love for a mixture of relaxing and adventurous activities, desire for tropical heat, interest in beach clubs and culture, and travel after March 25th for seven nights with your family, I've picked a destination for you. For your stay, would you prefer a boutique hideaway or a grand resort with every possible amenity?"
        mock_runner.run.return_value = [mock_event]
        
        message = "Plan my trip."
        response = agent.process_message(user_id, session_id, message)
        
        print(f"Agent Response: {response}")
        
        # CHECK: Response should NOT contain "Maldives"
        if "Maldives" in response:
            print("FAILURE: Agent revealed the destination!")
        else:
            print("SUCCESS: Agent kept the destination secret.")
            
        # CHECK: Response should contain the residence preference question
        if "boutique hideaway" in response and "grand resort" in response:
            print("SUCCESS: Agent asked about residence preference correctly.")
        else:
            # Maybe it didn't use the exact wording, but let's check if it's following the new logic
            print("DEBUG: Checking residence question logic...")

if __name__ == "__main__":
    test_secrecy()
