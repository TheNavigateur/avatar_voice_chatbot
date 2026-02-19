#!/usr/bin/env python3
import os
import sys
import uuid
import logging

# Add current directory to path
sys.path.append(os.getcwd())

from agent import voice_agent
from booking_service import BookingService
from models import PackageType, BookingStatus
from database import get_db_connection

# Configure logging to be less verbose for cleaner output
logging.getLogger('agent').setLevel(logging.WARNING)
logging.getLogger('google_adk').setLevel(logging.WARNING)

def setup_booked_holidays(user_id, count=1):
    session_id = str(uuid.uuid4())
    packages = []
    
    # Initialize DB (creates tables)
    from database import init_db
    init_db()
    
    for i in range(count):
        title = f"Holiday {i+1} to {'Maldives' if i==0 else 'Paris' if i==1 else 'Dubai'}"
        pkg = BookingService.create_package(session_id, title, PackageType.HOLIDAY, user_id=user_id)
        
        # Now update status in a separate transaction
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED.value, pkg.id))
        conn.commit()
        conn.close()
        packages.append(pkg)
    
    return packages

def test_shopping_flow(user_id, scenario_name, holiday_count):
    print(f"\n--- Scenario: {scenario_name} ({holiday_count} holiday(s)) ---")
    session_id = str(uuid.uuid4())
    setup_booked_holidays(user_id, holiday_count)
    
    query = "I want to shop for my holiday"
    print(f"User: {query}")
    resp = voice_agent.process_message(user_id, session_id, query)
    print(f"Agent: {resp}")
    
    return resp

def reproduce():
    # Use a fresh test database
    os.environ["DB_NAME"] = "test_repro.db"
    if os.path.exists("test_repro.db"):
        os.remove("test_repro.db")
        
    user_id_single = "repro_single_" + str(uuid.uuid4())[:8]
    user_id_multi = "repro_multi_" + str(uuid.uuid4())[:8]
    
    # Test with 1 holiday
    resp_single = test_shopping_flow(user_id_single, "Single Holiday", 1)
    
    # Test with 2 holidays
    resp_multi = test_shopping_flow(user_id_multi, "Multiple Holidays", 2)

if __name__ == "__main__":
    reproduce()
