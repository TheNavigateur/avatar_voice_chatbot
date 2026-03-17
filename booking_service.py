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
                description=row['description'],
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
                description=row['description'],
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
            description=row['description'] if 'description' in row.keys() else None,
            type=PackageType(row['type']),
            status=BookingStatus(row['status']),
            total_price=row['total_price'],
            booking_window_opens_at=row['booking_window_opens_at'],
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
    def create_package(session_id: str, title: str, description: str = None, type: PackageType = PackageType.MIXED, user_id: str = "web_user", status: BookingStatus = BookingStatus.DRAFT, booking_window_opens_at: str = None) -> Package:
        conn = get_db_connection()
        c = conn.cursor()
        
        new_id = str(uuid.uuid4())
        c.execute("""
            INSERT INTO packages (id, session_id, user_id, title, description, type, status, total_price, booking_window_opens_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_id, session_id, user_id, title, description, type.value, status.value, 0.0, booking_window_opens_at))
        
        conn.commit()
        conn.close()
        
        # Return object
        return Package(id=new_id, session_id=session_id, user_id=user_id, title=title, description=description, type=type, status=status, booking_window_opens_at=booking_window_opens_at)

    @staticmethod
    def add_item_to_package(session_id: str, package_id: str, item: PackageItem) -> Optional[Package]:
        return BookingService.add_items_to_package(session_id, package_id, [item])

    @staticmethod
    def add_items_to_package(session_id: str, package_id: str, items: List[PackageItem]) -> Optional[Package]:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Verify package exists
        c.execute("SELECT id, session_id FROM packages WHERE id = ?", (package_id,))
        pkg_row = c.fetchone()
        if not pkg_row:
            conn.close()
            return None
            
        actual_session_id = pkg_row['session_id']

        # Get existing items for de-duplication check
        c.execute("SELECT name, price, description FROM package_items WHERE package_id = ?", (package_id,))
        existing_items = {(r['name'], r['price'], r['description']) for r in c.fetchall()}

        for item in items:
            # Skip if exact match already exists (safety net)
            if (item.name, item.price, item.description) in existing_items:
                logger.info(f"[SERVICE] Skipping duplicate item: {item.name}")
                continue
                
            c.execute("""
                INSERT INTO package_items (id, package_id, name, item_type, price, status, description, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item.id, package_id, item.name, item.item_type, item.price, item.status, item.description, json.dumps(item.metadata)))
            
            # Add to set to prevent duplicates within the same batch
            existing_items.add((item.name, item.price, item.description))
        
        # Update total price of package
        c.execute("SELECT sum(price) as total FROM package_items WHERE package_id = ?", (package_id,))
        res = c.fetchone()
        new_total = res['total'] if res['total'] else 0.0
        
        c.execute("UPDATE packages SET total_price = ? WHERE id = ?", (new_total, package_id))
        
        conn.commit()
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
    async def execute_booking(package: Package, user_email: str, travelers: List[Dict]) -> Dict:
        """
        Executes real booking for a package.
        Flights & Hotels (if IDs exist) -> Duffel API
        Everything else -> Affilate deep-links
        """
        from services.duffel_service import DuffelService
        from services.email_service import EmailService
        
        duffel = DuffelService()
        success_items = []
        failed_items = []
        
        conn = get_db_connection()
        c = conn.cursor()
        
        for item in package.items:
            try:
                # Skip already booked items
                if item.status == BookingStatus.BOOKED:
                    logger.info(f"Item {item.name} is already booked. Skipping.")
                    success_items.append(item)
                    continue

                logger.info(f"Processing booking for: {item.name} ({item.item_type})")
                
                # 1. Flights (Duffel API with fallback)
                if item.item_type == 'flight':
                    offer_id = item.metadata.get('offer_id')
                    if offer_id:
                        order = duffel.create_order(offer_id, travelers)
                        if order and 'id' in order:
                            item.metadata['booking_reference'] = order.get('booking_reference')
                            item.metadata['duffel_order_id'] = order.get('id')
                            item.status = BookingStatus.BOOKED
                        else:
                            # Fallback if API call fails
                            item.status = BookingStatus.PENDING_EXTERNAL
                            logger.info(f"Duffel Flight API failed for {item.name}, falling back to external link.")
                    else:
                        # FALLBACK: No direct booking ID found.
                        item.status = BookingStatus.PENDING_EXTERNAL
                        logger.info(f"No Duffel Offer ID for {item.name}, setting to PENDING_EXTERNAL.")

                # 2. Hotels (Duffel Stays API with fallback)
                elif item.item_type == 'hotel':
                    stay_id = item.metadata.get('stay_id') or item.metadata.get('hotel_id') 
                    if stay_id and (stay_id.startswith('sta_') or stay_id.startswith('acc_')):
                        # For Stay bookings on Duffel
                        booking = duffel.create_stay_order(stay_id, travelers[0]) 
                        if booking and 'id' in booking:
                            item.metadata['booking_reference'] = booking.get('id')
                            item.status = BookingStatus.BOOKED
                        else:
                            # Fallback if API call fails but we has an ID
                            item.status = BookingStatus.PENDING_EXTERNAL
                            logger.info(f"Duffel Stays API failed for {item.name}, falling back to external link.")
                    else:
                        # FALLBACK: No direct booking ID found.
                        item.status = BookingStatus.PENDING_EXTERNAL
                        logger.info(f"No Duffel ID for {item.name}, setting to PENDING_EXTERNAL for affiliate booking.")

                # 3. Activities (Travelpayouts Redirect)
                elif item.item_type == 'activity':
                    item.metadata['booking_link'] = BookingService.build_travelpayouts_viator_link(item)
                    item.status = BookingStatus.PENDING_EXTERNAL
                    # Also record a placeholder for verification if we had an API key
                    # For now, it stays as pending_external

                # 4. Restaurants (OpenTable Redirect)
                elif item.item_type == 'restaurant':
                    item.metadata['booking_link'] = BookingService.build_opentable_link(item)
                    item.status = BookingStatus.PENDING_EXTERNAL

                # 5. Products (Amazon Redirect)
                elif item.item_type == 'product':
                    # Already has booking_link in metadata usually
                    item.status = BookingStatus.BOOKED

                # Update item in DB
                c.execute("UPDATE package_items SET status = ?, metadata = ? WHERE id = ?", 
                          (item.status.value, json.dumps(item.metadata), item.id))
                
                if item.status == BookingStatus.BOOKED:
                    success_items.append(item)

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Error booking {item.name}: {error_msg}")
                item.status = BookingStatus.FAILED
                failed_items.append(item)
                # Keep track of the first error message to return
                if 'first_error' not in locals():
                    first_error = error_msg
        
        # Update Package Level Status
        if failed_items:
            package.status = BookingStatus.FAILED if not success_items and not any(i.status == BookingStatus.PENDING_EXTERNAL for i in package.items) else BookingStatus.PARTIAL
        elif any(i.status == BookingStatus.PENDING_EXTERNAL for i in package.items):
            package.status = BookingStatus.PARTIAL
        else:
            package.status = BookingStatus.BOOKED
            
        c.execute("UPDATE packages SET status = ? WHERE id = ?", (package.status.value, package.id))
        conn.commit()
        conn.close()

        # Trigger Email if any successes
        from services.notification_service import NotificationService
        if success_items:
            try:
                # Re-serialize for email helper
                pkg_dict = package.dict() if hasattr(package, 'dict') else package.__dict__
                NotificationService.send_booking_confirmation(user_email, pkg_dict)
            except Exception as e:
                logger.error(f"Failed to trigger booking email: {e}")

        msg = "Booking processed."
        if failed_items:
            # Use the captured error message if available
            msg = f"Booking failed for {failed_items[0].name}: {locals().get('first_error', 'General error')}"
            if len(failed_items) > 1:
                msg += f" (and {len(failed_items)-1} other items)"

        return {
            "status": "success" if not failed_items else "partial",
            "message": msg,
            "success_count": len(success_items),
            "failed_count": len(failed_items)
        }

    @staticmethod
    def verify_item_booking(user_id: str, package_id: str, item_id: str) -> Dict:
        """
        Manually marks an item as BOOKED. Used for external redirects.
        """
        conn = get_db_connection()
        c = conn.cursor()
        
        # 1. Update the item
        c.execute("UPDATE package_items SET status = ? WHERE id = ? AND package_id = ?", 
                  (BookingStatus.BOOKED.value, item_id, package_id))
        
        # 2. Re-fetch all items for this package to determine package status
        c.execute("SELECT status FROM package_items WHERE package_id = ?", (package_id,))
        rows = c.fetchall()
        item_statuses = [row[0] for row in rows]
        
        new_package_status = BookingStatus.BOOKED
        # Note: If any remain as 'pending_external', the package is still 'partial'
        if any(s == BookingStatus.FAILED.value for s in item_statuses):
            new_package_status = BookingStatus.PARTIAL
        elif any(s == BookingStatus.PENDING_EXTERNAL.value for s in item_statuses):
            new_package_status = BookingStatus.PARTIAL
        elif any(s == BookingStatus.DRAFT.value for s in item_statuses):
            new_package_status = BookingStatus.DRAFT

        # 3. Update the package
        c.execute("UPDATE packages SET status = ? WHERE id = ?", (new_package_status.value, package_id))
        
        conn.commit()
        conn.close()
        
        return {
            "status": "success",
            "item_status": BookingStatus.BOOKED.value,
            "package_status": new_package_status.value
        }

    @staticmethod
    def sync_external_bookings(user_id: str, package_id: str) -> Dict:
        """
        Polls Travelpayouts Statistics API for paid bookings matching our SubIDs.
        """
        token = os.environ.get("TRAVELPAYOUTS_API_TOKEN")
        if not token:
            return {"status": "error", "message": "TRAVELPAYOUTS_API_TOKEN not set."}

        conn = get_db_connection()
        c = conn.cursor()
        
        # 1. Get all pending external items for this package
        c.execute("SELECT id FROM package_items WHERE package_id = ? AND status = ?", 
                  (package_id, BookingStatus.PENDING_EXTERNAL.value))
        pending_ids = [row[0] for row in c.fetchall()]
        
        if not pending_ids:
            return {"status": "success", "updates": 0, "message": "No pending external items to verify."}

        # 2. Call Travelpayouts Statistics API
        # We check the last 30 days to be safe
        import datetime
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=30)
        
        url = "https://api.tp.st/v2/statistics/actions"
        headers = {"X-Access-Token": token}
        params = {
            "date_from": start_date.strftime("%Y-%m-%d"),
            "date_to": end_date.strftime("%Y-%m-%d"),
            "limit": 100
        }
        
        try:
            import requests
            response = requests.get(url, headers=headers, params=params, timeout=10)
            if response.status_code != 200:
                logger.error(f"Travelpayouts API Error {response.status_code}: {response.text}")
                return {"status": "error", "message": f"API error: {response.status_code}"}
            
            data = response.json()
            actions = data.get("actions", [])
            
            # Map sub_id to action status
            # We look for "paid" or "confirmed" states
            completed_subids = set()
            for action in actions:
                subid = action.get("sub_id")
                state = action.get("state") # e.g. "paid", "confirmed", "pending"
                if subid in pending_ids and state in ["paid", "confirmed"]:
                    completed_subids.add(subid)
            
            # 3. Update database for matched SubIDs
            update_count = 0
            for subid in completed_subids:
                c.execute("UPDATE package_items SET status = ? WHERE id = ?", 
                          (BookingStatus.BOOKED.value, subid))
                update_count += 1
            
            if update_count > 0:
                # Recalculate package status
                c.execute("SELECT status FROM package_items WHERE package_id = ?", (package_id,))
                item_statuses = [row[0] for row in c.fetchall()]
                
                new_pkg_status = BookingStatus.BOOKED
                if any(s == BookingStatus.FAILED.value for s in item_statuses):
                    new_pkg_status = BookingStatus.PARTIAL
                elif any(s == BookingStatus.PENDING_EXTERNAL.value for s in item_statuses):
                    new_pkg_status = BookingStatus.PARTIAL
                elif any(s == BookingStatus.DRAFT.value for s in item_statuses):
                    new_pkg_status = BookingStatus.DRAFT
                
                c.execute("UPDATE packages SET status = ? WHERE id = ?", (new_pkg_status.value, package_id))
            
            conn.commit()
            conn.close()
            
            return {
                "status": "success", 
                "updates": update_count, 
                "message": f"Sync complete. {update_count} items updated."
            }
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return {"status": "error", "message": f"Sync failed: {str(e)}"}
    @staticmethod
    def build_duffel_search_link(item: PackageItem) -> str:
        # Simplified redirect to Duffel's search UI if we have one, or just Google Flights
        return f"https://www.google.com/travel/flights?q=flights+to+{item.metadata.get('destination', 'destination')}"

    @staticmethod
    def build_travelpayouts_hotel_link(item: PackageItem) -> str:
        marker = "507481"
        city = item.metadata.get('location', '')
        # Simple Search link for Booking.com via Travelpayouts with SubID
        base_url = "https://www.booking.com/searchresults.html"
        params = f"?ss={city}&marker={marker}&aid=2312000&subid={item.id}"
        return base_url + params

    @staticmethod
    def build_travelpayouts_viator_link(item: PackageItem) -> str:
        # The user has Partner ID P00292499
        partner_id = "P00292499"
        name = item.name.replace(" ", "+")
        # Include item ID as SubID for automated tracking
        return f"https://www.viator.com/partner/{partner_id}/search/{name}?subid={item.id}"

    @staticmethod
    def build_opentable_link(item: PackageItem) -> str:
        name = item.name.replace(" ", "+")
        return f"https://www.opentable.com/s/?term={name}"

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
        Returns a concise natural language summary of the user's packages, 
        pruning old entries to save context space.
        """
        all_packages = BookingService.get_user_packages(user_id)
        if not all_packages:
            return "You don't have any packages saved yet."
            
        # Limit detailed summary to most recent 10 packages
        recent_limit = 10
        packages = all_packages[:recent_limit]
        older_count = len(all_packages) - recent_limit
        
        summary = f"I found {len(all_packages)} packages in total"
        if older_count > 0:
            summary += f" (showing the {recent_limit} most recent):\n"
        else:
            summary += ":\n"

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
                    
            summary += f"- '{p.title}' [SYSTEM_ID: {p.id}] Status: {p.status.value.capitalize()}, Date: {pkg_date}{content_str}\n"
            
        if older_count > 0:
            older_titles = [f"'{p.title}'" for p in all_packages[recent_limit:recent_limit+5]]
            summary += f"- ... and {older_count} older packages (including: {', '.join(older_titles)})\n"

        summary += " (Note to Agent: The '[SYSTEM_ID: ...]' is for your tool calls ONLY. DO NOT speak or print it. If you want to open one, use the ID with '[NAVIGATE_TO_PACKAGE: id]')\n"
        summary += "Which one would you like to show? Use the navigation protocol to open it for them."
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
            
        summary = f"[SYSTEM_ID: {pkg.id}] (Note to Agent: Use '[NAVIGATE_TO_PACKAGE: {pkg.id}]' if asked to open this view)\n"
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

    @staticmethod
    def delete_package(package_id: str):
        """
        Deletes a package and all its associated items.
        """
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM package_items WHERE package_id = ?", (package_id,))
        c.execute("DELETE FROM packages WHERE id = ?", (package_id,))
        conn.commit()
        conn.close()
        logger.info(f"Deleted package {package_id} and all its items.")
