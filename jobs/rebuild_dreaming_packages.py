import os
import logging
from datetime import datetime
from database import get_db_connection
from booking_service import BookingService
from services.notification_service import NotificationService
from models import BookingStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_and_rebuild_dreaming_packages():
    """
    Finds all 'dreaming' packages whose booking window has opened and notifies the user.
    This script could be run daily via a cron job.
    """
    logger.info("Checking for 'dreaming' packages with opened booking windows...")
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Find dreaming packages where current date >= booking_window_opens_at
    today = datetime.now().strftime("%Y-%m-%d")
    c.execute("""
        SELECT id, session_id, user_id, title, booking_window_opens_at 
        FROM packages 
        WHERE status = ? AND booking_window_opens_at <= ?
    """, (BookingStatus.DREAMING.value, today))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        logger.info("No dreaming packages require updates today.")
        return

    for row in rows:
        pkg_id = row['id']
        title = row['title']
        user_id = row['user_id']
        
        logger.info(f"Booking window opened for '{title}' ({pkg_id}). Notifying user...")
        
        # 1. Update status to DRAFT (now bookable)
        # In a real implementation, we might also trigger a background task to call the agent 
        # to "re-build" it with real items. For now, we update the status.
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.DRAFT.value, pkg_id))
        conn.commit()
        conn.close()
        
        # 2. Send Notification
        NotificationService.send_booking_window_opened_email(user_id, title, pkg_id)

if __name__ == "__main__":
    check_and_rebuild_dreaming_packages()
