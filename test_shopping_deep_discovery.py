#!/usr/bin/env python3
"""
Test script for shopping deep discovery flow.
This simulates the complete flow from checklist to product selection.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import voice_agent
from booking_service import BookingService
from models import Package, PackageItem, PackageType, BookingStatus
import uuid

def test_shopping_deep_discovery():
    """Test the shopping deep discovery flow"""
    
    print("=" * 80)
    print("SHOPPING DEEP DISCOVERY FLOW TEST")
    print("=" * 80)
    
    # Setup
    user_id = "test_user_shopping"
    session_id = str(uuid.uuid4())
    
    # Step 1: Create a booked holiday package
    print("\n[1] Creating a booked beach holiday package...")
    pkg = BookingService.create_package(
        session_id=session_id,
        title="Maldives Beach Holiday",
        package_type=PackageType.HOLIDAY,
        user_id=user_id
    )
    
    # Add some travel items
    flight = PackageItem(
        name="Flight to Maldives",
        item_type="flight",
        price=450.0,
        description="Direct flight from London"
    )
    hotel = PackageItem(
        name="Beach Resort",
        item_type="hotel",
        price=1200.0,
        description="5-star beachfront resort"
    )
    
    BookingService.add_item_to_package(session_id, pkg.id, flight)
    BookingService.add_item_to_package(session_id, pkg.id, hotel)
    
    # Book the package
    pkg.status = BookingStatus.BOOKED
    print(f"✓ Created and booked package: {pkg.title} (ID: {pkg.id})")
    
    # Step 2: Trigger shopping flow
    print("\n[2] Triggering shopping flow...")
    response1 = voice_agent.process_message(
        user_id=user_id,
        session_id=session_id,
        message="Hi!",
        region="UK"
    )
    print(f"Agent: {response1[:200]}...")
    
    # Check if shopping offer is made
    if "shopping" in response1.lower() or "items" in response1.lower():
        print("✓ Agent offered shopping flow")
    else:
        print("⚠ Agent did not offer shopping flow")
    
    # Step 3: Accept shopping offer
    print("\n[3] Accepting shopping offer...")
    response2 = voice_agent.process_message(
        user_id=user_id,
        session_id=session_id,
        message="Yes, I'd like to see the shopping list",
        region="UK"
    )
    print(f"Agent: {response2[:300]}...")
    
    # Check for checklist
    if "[SHOPPING_CHECKLIST]" in response2:
        print("✓ Agent generated shopping checklist")
        
        # Extract checklist items
        import re
        match = re.search(r'\[SHOPPING_CHECKLIST\]([\s\S]*?)\[/SHOPPING_CHECKLIST\]', response2)
        if match:
            import json
            try:
                checklist_data = json.loads(match.group(1))
                items = checklist_data.get('items', [])
                print(f"  Checklist has {len(items)} items:")
                for item in items[:3]:
                    print(f"    - {item['name']} (status: {item['status']})")
            except:
                print("  Could not parse checklist JSON")
    else:
        print("⚠ No shopping checklist found")
        return
    
    # Step 4: Continue with checklist (simulating user marking items as "need")
    print("\n[4] Continuing after checklist...")
    response3 = voice_agent.process_message(
        user_id=user_id,
        session_id=session_id,
        message="I've updated the checklist. Let's continue.",
        region="UK"
    )
    print(f"Agent: {response3[:300]}...")
    
    # Check for deep discovery questions
    questions = [
        "size", "colour", "color", "style", "preference", "budget", "brand", "material"
    ]
    if any(q in response3.lower() for q in questions):
        print("✓ Agent asked deep discovery question")
    else:
        print("⚠ No deep discovery question detected")
    
    # Step 5: Answer a question (e.g., size for swimwear)
    print("\n[5] Answering deep discovery question...")
    response4 = voice_agent.process_message(
        user_id=user_id,
        session_id=session_id,
        message="I need size Large",
        region="UK"
    )
    print(f"Agent: {response4[:300]}...")
    
    # Step 6: Check if tools were used
    print("\n[6] Checking for Amazon search activity...")
    # The agent should be using search_amazon and check_amazon_stock
    # We can't directly check this without inspecting logs, but we can see if products were added
    
    # Step 7: Check final package
    print("\n[7] Checking final package state...")
    updated_pkg = BookingService.get_package(session_id, pkg.id)
    if updated_pkg:
        product_items = [item for item in updated_pkg.items if item.item_type == "product"]
        print(f"  Package now has {len(product_items)} product items")
        
        for item in product_items:
            print(f"\n  Product: {item.name}")
            print(f"    Price: £{item.price}")
            if item.metadata.get('rating'):
                print(f"    Rating: {item.metadata['rating']}⭐")
            if item.metadata.get('rating_count'):
                print(f"    Rating Count: {item.metadata['rating_count']}")
                if item.metadata['rating_count'] >= 100:
                    print("    ✓ Meets 100+ rating requirement")
                else:
                    print("    ⚠ Does NOT meet 100+ rating requirement")
            if item.metadata.get('product_url'):
                print(f"    URL: {item.metadata['product_url'][:50]}...")
    
    # Check for SHOPPING_PACKAGE_COMPLETE tag
    if "[SHOPPING_PACKAGE_COMPLETE]" in response4:
        print("\n✓ SHOPPING_PACKAGE_COMPLETE tag found - navigation would trigger")
    
    print("\n" + "=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_shopping_deep_discovery()
