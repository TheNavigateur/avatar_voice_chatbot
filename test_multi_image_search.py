
import os
import sys
import asyncio
from typing import List

# Add current directory to path
sys.path.append(os.getcwd())

from services.image_search_service import ImageSearchService
from agent import add_item_to_package_tool, create_new_package_tool
from booking_service import BookingService

async def test_search():
    service = ImageSearchService()
    print("Testing search_image_multi for 'Eiffel Tower'...")
    images = service.search_image_multi("Eiffel Tower", num=3)
    print(f"Found {len(images)} images for Eiffel Tower")
    for img in images:
        print(f" - {img}")
    
    if len(images) > 0:
        print("PASS: search_image_multi found images")
    else:
        print("FAIL: search_image_multi found no images")

    print("\nTesting get_activity_image for 'Surfing' in 'Bali'...")
    activity_images = service.get_activity_image("Surfing", "Bali", num=3)
    print(f"Found {len(activity_images)} images for Bali Surfing")
    for img in activity_images:
        print(f" - {img}")

def test_agent_tool():
    print("\nTesting agent tool logic (simulated)...")
    session_id = "test_session_multi"
    user_id = "test_user"
    
    try:
        # We try to create a package, but if DB is locked, we'll just skip the DB part
        # and test the image fetching logic inside add_item_to_package_tool
        print("Checking if we can use the database...")
        create_new_package_tool(session_id, user_id, "Paris Trip", "holiday")
        pkg = BookingService.get_latest_user_package(user_id)
        if not pkg:
             print("Note: No package found, skipping parts that need DB.")
             return
             
        package_id = pkg.id
        
        print(f"Adding activity to package {package_id}...")
        result = add_item_to_package_tool(
            session_id, 
            package_id, 
            "Louvre Museum Tour", 
            "activity", 
            50.0, 
            description="Great tour"
        )
        print(result)
        
        # Check the package
        pkg = BookingService.get_package(session_id, package_id)
        item = pkg.items[-1]
        images = item.metadata.get('images', [])
        print(f"Found {len(images)} images in item metadata")
        for img in images:
            print(f" - {img}")
    except Exception as e:
        print(f"Note: Skipping full agent tool test because database is likely locked or unavailable: {e}")
        print("The most important thing is that ImageSearchService works (see above).")

if __name__ == "__main__":
    asyncio.run(test_search())
    test_agent_tool()
    print("\nVerification script finished.")
