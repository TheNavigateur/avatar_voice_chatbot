
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

def test_package_id_secrecy():
    agent = VoiceAgent()
    user_id = "test_user"
    session_id = "test_session"
    package_id = "e5be3a2f-3ee0-4cdf-afd0-1a757fb53477"
    
    # Mocking the tool output that currently includes [SYSTEM_ID: ...]
    # This matches what BookingService.get_package_details_summary returns now
    mock_summary = f"[SYSTEM_ID: {package_id}]\n### Maldives Beach Holiday\n**Status**: Booked\n**Total Price**: $1411.12\n\n#### Flights\n- **A flight to the Maldives** ($450.00)\n\n#### Hotels\n- **A beachfront resort** ($800.00)\n"
    
    with patch('booking_service.BookingService.get_package_details_summary', return_value=mock_summary), \
         patch('profile_service.ProfileService.get_profile', return_value="User likes Maldives."), \
         patch('agent.Runner') as mock_runner_class:
        
        mock_runner = mock_runner_class.return_value
        
        # Test Case: Agent should NOT reveal the ID even if it's in the system context
        mock_event = MagicMock()
        # Simulation of a "good" response that follows instructions
        mock_event.text = "Okay, here's what's included in your booked 'Maldives Beach Holiday': A flight to the Maldives for $450 and a beachfront resort for $800. The total is $1411.12."
        mock_runner.run.return_value = [mock_event]
        
        message = "Tell me about my Maldives trip."
        response = agent.process_message(user_id, session_id, message, package_id=package_id)
        
        print(f"Agent Response: {response}")
        
        # CHECK: Response should NOT contain the UUID or "[SYSTEM_ID"
        if package_id in response or "[SYSTEM_ID" in response or "INTERNALID" in response:
            print(f"FAILURE: Agent revealed the package ID! (ID: {package_id})")
        else:
            print("SUCCESS: Agent kept the package ID secret.")

if __name__ == "__main__":
    test_package_id_secrecy()
