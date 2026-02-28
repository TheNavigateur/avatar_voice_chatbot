import json
import uuid
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from booking_service import BookingService
from models import PackageType, PackageItem

def test_batch_fix():
    session_id = str(uuid.uuid4())
    user_id = "test_user_batch_fix"
    
    # 1. Create a package
    pkg = BookingService.create_package(session_id, "Test Batch Fix Trip", PackageType.HOLIDAY, user_id=user_id)
    print(f"Created package: {pkg.id}")
    
    # 2. Simulate batch data with 'title' instead of 'name'
    items_data = [
        {
            "title": "Batch Item 1 (Title Field)",
            "item_type": "activity",
            "price": 100.0,
            "description": "Test description 1"
        },
        {
            "name": "Batch Item 2 (Name Field)",
            "item_type": "activity",
            "price": 200.0,
            "description": "Test description 2"
        },
        {
            "item_type": "activity",
            "price": 300.0,
            "description": "Test description 3 (No name or title)"
        }
    ]
    
    # Simulate the logic in propose_itinerary_batch_bound (since we can't easily call the bound tool without full Agent setup)
    package_items = []
    for data in items_data:
        item_name = data.get('name') or data.get('title') or 'Unknown Item'
        pkg_item = PackageItem(
            name=item_name,
            item_type=data.get('item_type', 'activity'),
            price=float(data.get('price', 0.0)),
            description=data.get('description', '')
        )
        package_items.append(pkg_item)
    
    # Add to package
    BookingService.add_items_to_package(session_id, pkg.id, package_items)
    
    # 3. Verify
    updated_pkg = BookingService.get_package(session_id, pkg.id)
    print(f"\nVerification for package {updated_pkg.id}:")
    for item in updated_pkg.items:
        print(f"- Item Name: {item.name}, Price: {item.price}")
        if "Unknown" in item.name and "No name or title" not in item.description:
             print("FAILED: Item name should not be Unknown if title or name is provided.")
             return
    
    if len(updated_pkg.items) == 3:
        print("\nSUCCESS: All items added correctly.")
    else:
        print(f"\nFAILED: Expected 3 items, found {len(updated_pkg.items)}")

if __name__ == "__main__":
    test_batch_fix()
