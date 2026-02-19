import uuid
from booking_service import BookingService
from models import PackageItem, PackageType, BookingStatus
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_remove_item():
    session_id = f"test-session-{uuid.uuid4()}"
    user_id = "test_user"
    
    # 1. Create a package
    logger.info("Creating test package...")
    pkg = BookingService.create_package(session_id, "Test Removal Package", PackageType.SHOPPING, user_id=user_id)
    package_id = pkg.id
    logger.info(f"Package created: {package_id}")
    
    # 2. Add an item
    logger.info("Adding item to package...")
    item = PackageItem(name="Test Item", item_type="product", price=100.0)
    item_id = item.id
    pkg = BookingService.add_item_to_package(session_id, package_id, item)
    logger.info(f"Item added: {item_id}, Package total: {pkg.total_price}")
    
    assert len(pkg.items) == 1
    assert pkg.total_price == 100.0
    
    # 3. Add another item
    logger.info("Adding another item to package...")
    item2 = PackageItem(name="Test Item 2", item_type="product", price=50.0)
    item2_id = item2.id
    pkg = BookingService.add_item_to_package(session_id, package_id, item2)
    logger.info(f"Item 2 added: {item2_id}, Package total: {pkg.total_price}")
    
    assert len(pkg.items) == 2
    assert pkg.total_price == 150.0
    
    # 4. Remove the first item
    logger.info(f"Removing item {item_id}...")
    pkg = BookingService.remove_item_from_package(session_id, package_id, item_id)
    
    assert pkg is not None
    logger.info(f"Item removed. Remaining items: {len(pkg.items)}, Package total: {pkg.total_price}")
    
    assert len(pkg.items) == 1
    assert pkg.items[0].id == item2_id
    assert pkg.total_price == 50.0
    
    # 5. Remove the second item
    logger.info(f"Removing item {item2_id}...")
    pkg = BookingService.remove_item_from_package(session_id, package_id, item2_id)
    
    assert pkg is not None
    logger.info(f"Item removed. Remaining items: {len(pkg.items)}, Package total: {pkg.total_price}")
    
    assert len(pkg.items) == 0
    assert pkg.total_price == 0.0
    
    logger.info("Test passed successfully!")

if __name__ == "__main__":
    test_remove_item()
