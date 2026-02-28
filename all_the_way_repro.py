import os
import logging
from agent import voice_agent
from booking_service import BookingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_finalization_flow():
    user_id = "test_user_finalization_v12"
    session_id = "test_session_finalization_v12"
    current_time = "2026-02-22 12:00:00"
    
    # 1. Start trip
    print("\n--- Turn 1: Start ---")
    message = "Italy trip please!"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 2. Provide departure and date (FUTURE DATE May 2027)
    print("\n--- Turn 2: Departure and Date (May 2027) ---")
    message = "London, and May 2027"
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 3. Choose experience
    print("\n--- Turn 3: Choice/Experience ---")
    message = "Pasta-Making Class" 
    print(f"User: {message}")
    for chunk in voice_agent.process_message_stream(user_id, session_id, message, current_time=current_time):
        print(chunk, end="", flush=True)
    print()

    # 4. Final check of package
    print("\n--- Turn 4: Final Package Summary ---")
    summary = BookingService.get_user_packages_summary(user_id)
    print(f"DATABASE SUMMARY:\n{summary}")

if __name__ == "__main__":
    if not os.environ.get("GOOGLE_API_KEY"):
        print("Please set GOOGLE_API_KEY")
    else:
        test_finalization_flow()
