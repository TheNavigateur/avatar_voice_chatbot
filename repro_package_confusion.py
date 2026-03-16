#!/usr/bin/env python3
import os
import sys
import uuid
import logging
import json

# Add current directory to path
sys.path.append(os.getcwd())

from agent import VoiceAgent
from booking_service import BookingService
from models import PackageType, BookingStatus
from database import init_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reproduce_issue():
    # Ensure GOOGLE_API_KEY is set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("WARNING: GOOGLE_API_KEY not set. Attempting to source secrets.sh...")
        # Simple hack to read secrets.sh if it exists
        if os.path.exists("secrets.sh"):
            with open("secrets.sh", "r") as f:
                for line in f:
                    if line.startswith("export "):
                        key_val = line.replace("export ", "").strip().split("=")
                        if len(key_val) == 2:
                            os.environ[key_val[0]] = key_val[1].strip('"')

    # Use a fresh test database
    os.environ["DB_NAME"] = "repro_package.db"
    if os.path.exists("repro_package.db"):
        os.remove("repro_package.db")
    
    init_db()
    
    agent = VoiceAgent()
    user_id = "test_user_repro"
    session_id = "test_session_repro"
    
    # 1. Create a Gold Coast package first
    print("\n--- Step 1: Creating Gold Coast Package ---")
    # Provide all logistics and vibe upfront to ensure it builds
    # We use a very explicit prompt to force a build.
    resp1 = agent.process_message(user_id, session_id, "I want a Gold Coast holiday for 3 days in October. I'm flying from Sydney. I want a relaxing beach vibe with some surfing. Build the package now with a hotel and some surf lessons.")
    print(f"Agent Response 1: {resp1}")
    
    pkgs = BookingService.get_user_packages(user_id)
    if not pkgs:
        print("COULD NOT TRIGGER AGENT TO CREATE PACKAGE. Creating one manually to proceed with test.")
        BookingService.create_package(session_id, "Gold Coast Family Holiday Oct 2026", PackageType.HOLIDAY, user_id=user_id)
        pkgs = BookingService.get_user_packages(user_id)

    print(f"Current packages for user: {[p.title for p in pkgs]}")
    gold_coast_pkg = pkgs[0]
    print(f"Gold Coast Package ID: {gold_coast_pkg.id}")
    
    # 2. Now ask for a Skiing holiday in the same session.
    # We NO LONGER pass the package_id to see if the agent correctly creates a NEW one for a NEW intent.
    print("\n--- Step 2: Requesting Skiing Holiday (Testing Autonomy) ---")
    resp2 = agent.process_message(user_id, session_id, "Actually, I want to plan something else. I want a skiing holiday in the Swiss Alps for 5 days in February. I'm flying from London. Please build this for me with a ski resort and some ski passes.")
    print(f"Agent Response 2: {resp2}")
    
    # 3. Test Assumptions & Context Inheritance (Beach -> Ski)
    print("\n--- Step 3: Testing Assumptions & Context Inheritance ---")
    session_id_assume = "test_session_assume"
    # Create a fresh Gold Coast package for 10 days from Sydney
    print("Creating 10-day Gold Coast trip from Sydney...")
    agent.process_message(user_id, session_id_assume, "I want a 10-day Gold Coast holiday. I'm flying from Sydney. Relaxing beach vibe. Build it.")
    
    pkgs_a = BookingService.get_user_packages(user_id)
    gc_a_id = next(p.id for p in pkgs_a if "Gold Coast" in p.title)
    
    # Now switch to skiing vaguely - DON'T provide duration or origin
    print("Switching vaguely to skiing without duration/origin (Viewing Gold Coast)...")
    # Simulate being in the same session AND viewing the Gold Coast trip
    resp_a = agent.process_message(user_id, session_id_assume, "Actually, I've changed my mind. I want a skiing trip to Zermatt instead. When can we go?", package_id=gc_a_id)
    print(f"Agent Response Discovery: {resp_a}")
    
    # Check if the agent asked for duration/origin or assumed them
    pkgs_final = BookingService.get_user_packages(user_id)
    # A package should NOT have been created yet if discovery is working
    zermatt_pkgs = [p for p in pkgs_final if "Zermatt" in p.title]
    
    if zermatt_pkgs:
        print(f"FAILURE: Agent built/created Zermatt package {zermatt_pkgs[0].title} prematurely!")
        if "10" in zermatt_pkgs[0].title:
             print("CONFIRMED: Agent inherited '10 days' from previous package.")
    # 4. Final Verification: Providing details for the new intent
    print("\n--- Step 4: Providing Discovery Details for New Intent ---")
    # Provide the info the agent asked for
    resp_f = agent.process_message(user_id, session_id_assume, "I'll be flying from Sydney, for 5 days in January. Build it now.", package_id=gc_a_id)
    print(f"Agent Response Final Build: {resp_f}")
    
    pkgs_f = BookingService.get_user_packages(user_id)
    print(f"Final Packages: {[p.title for p in pkgs_f]}")
    
    zermatt_pkg = next((p for p in pkgs_f if "Zermatt" in p.title), None)
    gc_pkg = next((p for p in pkgs_f if "Gold Coast" in p.title), None)
    
    if not zermatt_pkg:
        print("FAILURE: Zermatt package was never created.")
    elif zermatt_pkg.id == gc_a_id:
        print("FAILURE: Zermatt package REUSED the Gold Coast ID!")
    else:
        # Check for item leakage
        leakage = False
        for item in gc_pkg.items:
            if "ski" in item.name.lower() or "zermatt" in item.name.lower():
                leakage = True
        
        if leakage:
            print("FAILURE: Ski items leaked into the Gold Coast package!")
        else:
            print("FINAL SUCCESS: New package created, and existing package remains isolated.")

    # 5. Test 'Make my holiday!' (Destination Sovereignty)
    print("\n--- Step 5: Testing 'Make my holiday!' (No Destination Provided) ---")
    session_id_sovereign = "test_session_sovereign"
    resp_s = agent.process_message(user_id, session_id_sovereign, "Make my holiday!")
    print(f"Agent Response Sovereign: {resp_s}")
    
    # Check if the agent asked for a destination
    lower_resp_s = resp_s.lower()
    
    # "Where from" or "Where departing from" is OK (Logistics: Origin)
    # But "Where are you going" or "Where to" is NOT OK.
    
    asking_destination = False
    if "destination" in lower_resp_s or "location" in lower_resp_s or "planning on going" in lower_resp_s or "which city" in lower_resp_s or "what place" in lower_resp_s:
        asking_destination = True
    
    # Check for "Where" NOT followed by "from" or "departing"
    import re
    if re.search(r'\bwhere\b', lower_resp_s):
         if not re.search(r'\bwhere\b.*?\b(from|departing)\b', lower_resp_s):
              asking_destination = True

    if asking_destination:
        print(f"FAILURE: Agent asked for destination: {resp_s}")
    else:
        # Check if it asked for logistics or vibe
        logistics_words = ["how long", "duration", "flying from", "departure", "when", "month", "departing from", "vibe", "style", "what kind", "what sort"]
        found_logistics = [word for word in logistics_words if word in lower_resp_s]
        if found_logistics:
             print(f"SUCCESS: Agent asked for discovery {found_logistics} without asking for destination.")
        else:
             print(f"WARNING: Agent didn't ask for a destination, but also didn't seem to ask for discovery: {resp_s}")

if __name__ == "__main__":
    reproduce_issue()
