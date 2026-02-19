import sys
import os
import logging
from booking_service import BookingService
from models import PackageType, PackageItem, BookingStatus
from agent import get_package_details_tool, search_packages_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_package_summary_flow():
    session_id = "test_session_123"
    user_id = "test_user_456"
    
    # 1. Create a package
    logger.info("Creating a test package...")
    pkg = BookingService.create_package(session_id, "Maldives Beach Holiday", PackageType.HOLIDAY, user_id=user_id)
    package_id = pkg.id
    
    # 2. Add some items
    logger.info("Adding items to the package...")
    BookingService.add_item_to_package(session_id, package_id, PackageItem(
        name="Flight to Male",
        item_type="flight",
        price=500.0,
        description="Emirates flight via Dubai"
    ))
    
    BookingService.add_item_to_package(session_id, package_id, PackageItem(
        name="Sun Siyam Iru Fushi",
        item_type="hotel",
        price=2000.0,
        description="Overwater villa with private pool"
    ))
    
    BookingService.add_item_to_package(session_id, package_id, PackageItem(
        name="Scuba Diving",
        item_type="activity",
        price=150.0,
        description="Morning dive at Manta Point",
        metadata={"date": "March 15, 2024"}
    ))
    
    # 3. Test search_packages_tool (should not contain ID)
    logger.info("Testing search_packages_tool...")
    search_summary = search_packages_tool(user_id, query="Maldives")
    logger.info(f"Search Summary:\n{search_summary}")
    
    if package_id in search_summary:
        print("FAIL: ID found in search summary!")
        # sys.exit(1) # Don't exit yet, let's see the rest
    else:
        print("SUCCESS: ID not found in search summary.")
        
    # 4. Test get_package_details_tool by name
    logger.info("Testing get_package_details_tool by name...")
    details_by_name = get_package_details_tool(user_id, "Maldives Beach Holiday")
    logger.info(f"Details by Name:\n{details_by_name}")
    
    if "Flight to Male" in details_by_name and "Sun Siyam Iru Fushi" in details_by_name and "Scuba Diving" in details_by_name:
        print("SUCCESS: Details by name contains all items.")
    else:
        print("FAIL: Details by name missing items.")
        
    # 5. Test get_package_details_tool by ID (internal fallback)
    logger.info("Testing get_package_details_tool by ID...")
    details_by_id = get_package_details_tool(user_id, package_id)
    logger.info(f"Details by ID:\n{details_by_id}")
    
    if "Flight to Male" in details_by_id:
        print("SUCCESS: Details by ID works.")
    else:
        print("FAIL: Details by ID failed.")

if __name__ == "__main__":
    test_package_summary_flow()
