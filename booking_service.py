import uuid
from typing import List, Optional, Dict
from models import Package, PackageItem, BookingStatus, PackageType
import logging

logger = logging.getLogger(__name__)

# In-memory storage for prototype
# Map session_id -> List[Package]
package_store: Dict[str, List[Package]] = {}

class BookingService:
    
    @staticmethod
    def get_packages(session_id: str) -> List[Package]:
        return package_store.get(session_id, [])

    @staticmethod
    def get_package(session_id: str, package_id: str) -> Optional[Package]:
        packages = package_store.get(session_id, [])
        for p in packages:
            if p.id == package_id:
                return p
        return None

    @staticmethod
    def create_package(session_id: str, title: str, type: PackageType = PackageType.MIXED) -> Package:
        if session_id not in package_store:
            package_store[session_id] = []
        
        new_package = Package(session_id=session_id, title=title, type=type)
        package_store[session_id].append(new_package)
        return new_package

    @staticmethod
    def add_item_to_package(session_id: str, package_id: str, item: PackageItem) -> Optional[Package]:
        package = BookingService.get_package(session_id, package_id)
        if package:
            package.items.append(item)
            package.calculate_total()
            return package
        return None

    @staticmethod
    async def execute_booking(package: Package) -> Dict:
        """
        Simulates booking all items in a package.
        Returns result dict.
        """
        success_items = []
        failed_items = []
        
        for item in package.items:
            try:
                # Simulate API call
                logger.info(f"Booking item: {item.name} ({item.item_type})")
                
                # Mock failure for specific items relative to "Test"
                if "fail" in item.name.lower():
                    raise Exception("Mock booking failure")
                
                item.status = BookingStatus.BOOKED
                success_items.append(item)
                
            except Exception as e:
                logger.error(f"Failed to book {item.name}: {e}")
                item.status = BookingStatus.FAILED
                failed_items.append(item)
        
        if failed_items:
            # Critical failure logic could go here
            # For now, if ANY fail, we might want to flag the package as PARTIAL or perform ROLLBACK
            # The prompt requested: "rollback it all back upon any critical failure"
            
            # Let's assume generic failures are critical for now unless specified
            logger.info("Critical failure detected. Rolling back...")
            await BookingService.rollback_booking(package, success_items)
            package.status = BookingStatus.FAILED
            return {"status": "failed", "message": "Booking failed. Transaction rolled back.", "failed_items": [i.name for i in failed_items]}
        else:
            package.status = BookingStatus.BOOKED
            return {"status": "success", "message": "All items booked successfully!"}

    @staticmethod
    async def rollback_booking(package: Package, booked_items: List[PackageItem]):
        """
        Reverses bookings for items that were successful.
        """
        for item in booked_items:
            logger.info(f"Rolling back item: {item.name}")
            item.status = BookingStatus.DRAFT # Reset to draft or cancelled
            # In real life, call refund API
            
        package.status = BookingStatus.FAILED
