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
        c.execute("SELECT * FROM packages WHERE session_id = ? ORDER BY rowid ASC", (session_id,))
        rows = c.fetchall()
        
        packages = []
        for row in rows:
            pkg_id = row['id']
            # Get items for this package
            c2 = conn.cursor()
            c2.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg_id,))
            item_rows = c2.fetchall()
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
                user_id=row['user_id'] if row['user_id'] else "web_user",
                title=row['title'],
                type=PackageType(row['type']),
                status=BookingStatus(row['status']),
                total_price=row['total_price'],
                items=items
            ))
        conn.close()
        return packages

    @staticmethod
    def get_user_packages(user_id: str) -> List[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        # If user_id is web_user, also include legacy packages with no user_id
        if user_id == "web_user":
            c.execute("SELECT * FROM packages WHERE user_id = ? OR user_id IS NULL OR user_id = '' ORDER BY rowid DESC", (user_id,))
        else:
            c.execute("SELECT * FROM packages WHERE user_id = ? ORDER BY rowid DESC", (user_id,))
        rows = c.fetchall()
        
        packages = []
        for row in rows:
            pkg_id = row['id']
            # Get items for this package
            c2 = conn.cursor()
            c2.execute("SELECT * FROM package_items WHERE package_id = ?", (pkg_id,))
            item_rows = c2.fetchall()
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
                user_id=row['user_id'] if row['user_id'] else "web_user",
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
            user_id=row['user_id'] if row['user_id'] else "web_user",
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
    def get_booked_packages(user_id: str) -> List[Package]:
        """Retrieves all recently booked packages for a user."""
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, session_id FROM packages WHERE user_id = ? AND status = ? ORDER BY rowid DESC", (user_id, BookingStatus.BOOKED.value))
        rows = c.fetchall()
        conn.close()
        
        packages = []
        for row in rows:
            pkg = BookingService.get_package(row['session_id'], row['id'])
            if pkg:
                packages.append(pkg)
        return packages

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
    def remove_item_from_package(session_id: str, package_id: str, item_id: str) -> Optional[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify package exists
        c.execute("SELECT session_id FROM packages WHERE id = ?", (package_id,))
        pkg_row = c.fetchone()
        if not pkg_row:
            conn.close()
            return None
            
        actual_session_id = pkg_row['session_id']
        
        # Delete the item
        c.execute("DELETE FROM package_items WHERE id = ? AND package_id = ?", (item_id, package_id))
        
        # Update total price of package
        c.execute("SELECT sum(price) as total FROM package_items WHERE package_id = ?", (package_id,))
        res = c.fetchone()
        new_total = res['total'] if res['total'] else 0.0
        
        c.execute("UPDATE packages SET total_price = ? WHERE id = ?", (new_total, package_id))
        
        conn.commit()
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

    @staticmethod
    def search_packages(user_id: str, query: str = None, start_date: str = None, end_date: str = None, package_type: str = None) -> List[Package]:
        """
        Searches for packages based on criteria.
        """
        conn = get_db_connection()
        c = conn.cursor()
        
        sql = "SELECT * FROM packages WHERE (user_id = ? OR user_id IS NULL OR user_id = '')"
        params = [user_id]
        
        if query:
            sql += " AND (title LIKE ?)"
            params.append(f"%{query}%")
            
        if package_type:
            sql += " AND type = ?"
            params.append(package_type)
            
        sql += " ORDER BY rowid DESC"
        
        c.execute(sql, params)
        rows = c.fetchall()
        
        packages = []
        for row in rows:
            pkg = BookingService.get_package(row['session_id'], row['id'])
            if pkg:
                # Date filtering (simple check in metadata)
                if start_date or end_date:
                    matches_date = False
                    for item in pkg.items:
                        item_date_str = item.metadata.get('date') or item.metadata.get('check_in')
                        if item_date_str:
                            # Try to see if it matches year/month if simple string
                            if start_date and start_date in item_date_str: matches_date = True
                            if end_date and end_date in item_date_str: matches_date = True
                    if not matches_date:
                        continue
                packages.append(pkg)
                
        conn.close()
        return packages

    @staticmethod
    def get_user_packages_summary(user_id: str) -> str:
        """
        Returns a concise natural language summary of the user's packages.
        """
        packages = BookingService.get_user_packages(user_id)
        if not packages:
            return "You don't have any packages saved yet."
            
        summary = f"I found {len(packages)} packages in total:\n"
        for p in packages:
            # Create a brief content summary
            flights = len([i for i in p.items if i.item_type == 'flight'])
            hotels = len([i for i in p.items if i.item_type == 'hotel'])
            activities = len([i for i in p.items if i.item_type == 'activity'])
            products = len([i for i in p.items if i.item_type == 'product'])
            
            contents = []
            if flights: contents.append(f"{flights} flight{'s' if flights > 1 else ''}")
            if hotels: contents.append(f"{hotels} hotel{'s' if hotels > 1 else ''}")
            if activities: contents.append(f"{activities} activit{'ies' if activities > 1 else 'y'}")
            if products: contents.append(f"{products} product{'s' if products > 1 else ''}")
            
            content_str = f" ({', '.join(contents)})" if contents else " (Empty)"
            
            # Simple date extraction for the package from first item
            pkg_date = "No dates set"
            for item in p.items:
                d = item.metadata.get('date') or item.metadata.get('check_in')
                if d:
                    pkg_date = d
                    break
                    
            summary += f"- '{p.title}' (INTERNAL_ID: {p.id}) Status: {p.status.value.capitalize()}, Date: {pkg_date}{content_str}\n"
            
        summary += "\n(Note to Agent: The 'INTERNAL_ID' is for your tool calls only. DO NOT speak or print it in your response.)\n"
        summary += "Which one would you like to open? You can ask for more details on any draft or booked trip."
        return summary

    @staticmethod
    def get_package_by_title(user_id: str, title: str) -> Optional[Package]:
        """
        Finds a package for a user by its title, status keyword, or date month.
        """
        conn = get_db_connection()
        c = conn.cursor()
        
        query_lower = title.lower()
        words = query_lower.replace("'", "").replace('"', "").replace(",", "").replace(".", "").split()
        
        status_filter = None
        if "booked" in words: status_filter = 'booked'
        elif "draft" in words: status_filter = 'draft'
        elif "failed" in words: status_filter = 'failed'
        
        # Strip keywords for cleaner title match
        ignore_keywords = {"booked", "draft", "failed", "package", "trip", "holiday", "open", "the", "a", "show", "me", "my", "our", "please", "can", "you", "details", "for", "with", "about", "at", "to", "in", "of"}
        search_words = [w for w in words if w not in ignore_keywords]
        search_title = " ".join(search_words)
        
        if not search_title and status_filter:
             sql = "SELECT id, session_id FROM packages WHERE (user_id = ? OR user_id IS NULL OR user_id = '') AND status = ? ORDER BY rowid DESC LIMIT 1"
             params = (user_id, status_filter)
        elif status_filter:
             sql = "SELECT id, session_id FROM packages WHERE (user_id = ? OR user_id IS NULL OR user_id = '') AND title LIKE ? AND status = ? ORDER BY rowid DESC LIMIT 1"
             params = (user_id, f"%{search_title}%", status_filter)
        else:
             sql = "SELECT id, session_id FROM packages WHERE (user_id = ? OR user_id IS NULL OR user_id = '') AND title LIKE ? ORDER BY rowid DESC LIMIT 1"
             params = (user_id, f"%{search_title}%")
        
        c.execute(sql, params)
             
        row = c.fetchone()
        conn.close()
        
        if row:
            return BookingService.get_package(row['session_id'], row['id'])
        return None

    @staticmethod
    def get_package_details_summary(package_id: str) -> str:
        """
        Returns a detailed natural language summary of all items in a package.
        """
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT session_id, title, status, total_price FROM packages WHERE id = ?", (package_id,))
        pkg_row = c.fetchone()
        if not pkg_row:
            conn.close()
            return "Package not found."
            
        pkg = BookingService.get_package(pkg_row['session_id'], package_id)
        conn.close()
        
        if not pkg:
            return "Package not found."
            
        summary = f"(INTERNAL_ID: {pkg.id})\n"
        summary += f"### {pkg.title}\n"
        summary += f"**Status**: {pkg.status.value.capitalize()}\n"
        summary += f"**Total Price**: ${pkg.total_price:.2f}\n\n"
        
        if not pkg.items:
            summary += "This package is currently empty."
            return summary
            
        # Group items by type
        items_by_type = {}
        for item in pkg.items:
            t = item.item_type
            if t not in items_by_type:
                items_by_type[t] = []
            items_by_type[t].append(item)
            
        for itype, items in items_by_type.items():
            plural_type = itype.capitalize() + "s"
            if itype.lower() == 'activity':
                plural_type = "Activities"
            summary += f"#### {plural_type}\n"
            for item in items:
                summary += f"- **{item.name}**"
                if item.price > 0:
                    summary += f" (${item.price:.2f})"
                if item.description:
                    summary += f": {item.description}"
                
                # Add specific metadata if present
                if item.metadata.get('date'):
                    summary += f" (Date: {item.metadata['date']})"
                if item.metadata.get('rating'):
                    summary += f" (Rating: {item.metadata['rating']} stars)"
                summary += "\n"
            summary += "\n"
            
        return summary
