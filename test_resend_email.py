import os
import logging
from services.notification_service import NotificationService

# Set the key locally for this test run
os.environ["RESEND_API_KEY"] = "re_cjzUEDgq_9XRhwFyk7vHndQBPT2HkbRz8"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trigger_test_email():
    print("\n--- Triggering Test Email via Resend ---")
    user_email = "naveenchawla@gmail.com" # Using your profile email or the one you signed up with
    package_title = "Swiss Alps Ski Holiday Feb 2027"
    package_id = "test-uuid-123"
    
    success = NotificationService.send_booking_window_opened_email(user_email, package_title, package_id)
    
    if success:
        print("\nSUCCESS! Check your inbox (or spam folder) for the test email.")
    else:
        print("\nFAILURE. Check the logs above for the error from Resend.")

if __name__ == "__main__":
    trigger_test_email()
