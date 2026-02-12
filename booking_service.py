import uuid
from typing import List, Optional, Dict
from models import Package, PackageItem, BookingStatus, PackageType
import logging
from database import get_db_connection
import json

logger = logging.getLogger(__name__)

class BookingService:
    @staticmethod
    def get_packages(session_id: str) -> List[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM packages WHERE session_id = ?", (session_id,))
        rows = c.fetchall()
        
        packages = []
        for row in rows:
            pkg_id = row['id']
            # Get items for this package
            c.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg_id,))
            item_rows = c.fetchall()
            items = []
            for item in item_rows:
                try:
                    meta = json.loads(item['metadata']) if item['metadata'] else {}
                except:
                    meta = {}

                # Handle potentially missing status
                item_status = item['status'] if item['status'] else 'draft'

                items.append(PackageItem(
                    id=item['id'] if item['id'] else str(uuid.uuid4()),
                    name=item['name'],
                    item_type=item['item_type'],
                    price=item['price'],
                    status=BookingStatus(item_status),
                    description=item['description'],
                    metadata=meta
                ))
            
            packages.append(Package(
                id=pkg_id,
                session_id=row['session_id'],
                user_id=row['user_id'] if 'user_id' in row.keys() else "web_user",
                title=row['title'],
                type=PackageType(row['type']),
                status=BookingStatus(row['status']),
                total_price=row['total_price'],
                items=items
            ))
        conn.close()
        return packages

    @staticmethod
    def get_package(session_id: str, package_id: str) -> Optional[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM packages WHERE id = ? AND session_id = ?", (package_id, session_id))
        row = c.fetchone()
        
        if not row:
            conn.close()
            return None
        
        pkg_id = row['id']
        c.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg_id,))
        item_rows = c.fetchall()
        items = []
        for item in item_rows:
            try:
                meta = json.loads(item['metadata']) if item['metadata'] else {}
            except:
                meta = {}

            # Handle potentially missing status
            item_status = item['status'] if item['status'] else 'draft'

            items.append(PackageItem(
                id=item['id'] if item['id'] else str(uuid.uuid4()),
                name=item['name'],
                item_type=item['item_type'],
                price=item['price'],
                status=BookingStatus(item_status),
                description=item['description'],
                metadata=meta
            ))
        
        pkg = Package(
            id=pkg_id,
            session_id=row['session_id'],
            user_id=row['user_id'] if 'user_id' in row.keys() else "web_user",
            title=row['title'],
            type=PackageType(row['type']),
            status=BookingStatus(row['status']),
            total_price=row['total_price'],
            items=items
        )
        conn.close()
        return pkg

    @staticmethod
    def get_latest_user_package(user_id: str) -> Optional[Package]:
        """Retrieves the most recently modified draft package for a user."""
        conn = get_db_connection()
        c = conn.cursor()
        # In SQLite, we don't have rowids by default that are sorted by insertion if we use UUIDs, 
        # but packages are usually created in order. For better reliability, we use the rowid if we haven't added a created_at.
        # However, for now, we'll just take the last one added to the DB for that user.
        c.execute("SELECT id, session_id FROM packages WHERE user_id = ? AND status = ? ORDER BY rowid DESC LIMIT 1", (user_id, BookingStatus.DRAFT.value))
        row = c.fetchone()
        conn.close()
        
        if row:
            return BookingService.get_package(row['session_id'], row['id'])
        return None

    @staticmethod
    def get_latest_session_package(session_id: str) -> Optional[Package]:
        """Retrieves the most recently modified draft package for a specific session."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id FROM packages WHERE session_id = ? AND status = ? ORDER BY rowid DESC LIMIT 1", (session_id, BookingStatus.DRAFT.value))
        row = c.fetchone()
        conn.close()
        
        if row:
            return BookingService.get_package(session_id, row['id'])
        return None

    @staticmethod
    def get_latest_booked_package(user_id: str) -> Optional[Package]:
        """Retrieves the most recently booked package for a user."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, session_id FROM packages WHERE user_id = ? AND status = ? ORDER BY rowid DESC LIMIT 1", (user_id, BookingStatus.BOOKED.value))
        row = c.fetchone()
        conn.close()
        
        if row:
            return BookingService.get_package(row['session_id'], row['id'])
        return None

    @staticmethod
    def create_package(session_id: str, title: str, type: PackageType = PackageType.MIXED, user_id: str = "web_user") -> Package:
        conn = get_db_connection()
        c = conn.cursor()
        
        new_id = str(uuid.uuid4())
        c.execute("""
            INSERT INTO packages (id, session_id, user_id, title, type, status, total_price)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (new_id, session_id, user_id, title, type.value, BookingStatus.DRAFT.value, 0.0))
        
        conn.commit()
        conn.close()
        
        # Return object
        return Package(id=new_id, session_id=session_id, user_id=user_id, title=title, type=type)

    @staticmethod
    def add_item_to_package(session_id: str, package_id: str, item: PackageItem) -> Optional[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify package exists (using package_id which is unique)
        c.execute("SELECT id FROM packages WHERE id = ?", (package_id,))
        if not c.fetchone():
            conn.close()
            return None
            
        c.execute("""
            INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (item.id, package_id, item.name, item.item_type, item.price, item.status, item.description, json.dumps(item.metadata)))
        
        # Update total price of package
        # Simplified: sum query
        c.execute("SELECT sum(price) as total FROM package_items WHERE package_id = ?", (package_id,))
        res = c.fetchone()
        new_total = res['total'] if res['total'] else 0.0
        
        c.execute("UPDATE packages SET total_price = ? WHERE id = ?", (new_total, package_id))
        
        conn.commit()
        conn.close()
        
        # Note: We still return based on the NEW session_id if we want, but get_package uses session_id for filtering.
        # So we should probably find the actual session_id of the package to return it.
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT session_id FROM packages WHERE id = ?", (package_id,))
        actual_session_id = c.fetchone()['session_id']
        conn.close()
        
        return BookingService.get_package(actual_session_id, package_id)

    @staticmethod
    async def execute_booking(package: Package) -> Dict:
        """
        Simulates booking all items in a package.
        Returns result dict.
        """
        conn = get_db_connection()
        c = conn.cursor()
        
        success_items = []
        failed_items = []
        
        # Re-fetch items from DB to be safe
        # Or just use package.items provided
        
        for item in package.items:
            try:
                # Simulate API call
                logger.info(f"Booking item: {item.name} ({item.item_type})")
                
                # Mock failure for specific items relative to "Test"
                if "fail" in item.name.lower():
                    raise Exception("Mock booking failure")
                
                # Update DB status
                c.execute("UPDATE package_items SET status = ? WHERE id = ?", (BookingStatus.BOOKED, item.id))
                item.status = BookingStatus.BOOKED
                success_items.append(item)
                
            except Exception as e:
                logger.error(f"Failed to book {item.name}: {e}")
                # Update DB status
                c.execute("UPDATE package_items SET status = ? WHERE id = ?", (BookingStatus.FAILED, item.id))
                item.status = BookingStatus.FAILED
                failed_items.append(item)
        
        conn.commit() # Commit partial progress
        conn.close()
        
        if failed_items:
            logger.info("Critical failure detected. Rolling back...")
            await BookingService.rollback_booking(package, success_items)
            
            # Update Package Status
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.FAILED, package.id))
            conn.commit()
            conn.close()
            
            package.status = BookingStatus.FAILED
            return {"status": "failed", "message": "Booking failed. Transaction rolled back.", "failed_items": [i.name for i in failed_items]}
        else:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE packages SET status = ? WHERE id = ?", (BookingStatus.BOOKED, package.id))
            conn.commit()
            conn.close()
            
            package.status = BookingStatus.BOOKED
            return {"status": "success", "message": "All items booked successfully!"}

    @staticmethod
    async def rollback_booking(package: Package, booked_items: List[PackageItem]):
        """
        Reverses bookings for items that were successful.
        """
        conn = get_db_connection()
        c = conn.cursor()
        for item in booked_items:
            logger.info(f"Rolling back item: {item.name}")
            c.execute("UPDATE package_items SET status = ? WHERE id = ?", (BookingStatus.DRAFT, item.id))
            item.status = BookingStatus.DRAFT
        conn.commit()
        conn.close()
        
        package.status = BookingStatus.FAILED
