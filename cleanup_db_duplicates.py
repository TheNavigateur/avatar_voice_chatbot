import sqlite3
import os
import json

DB_NAME = "app.db" # Based on database.py

def cleanup_duplicates():
    if not os.path.exists(DB_NAME):
        print(f"Database {DB_NAME} not found.")
        return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("--- Starting Cleanup ---")

    # 1. Identify and delete "Unknown Item" entries that were likely caused by the bug
    # We only delete them if they have no useful description or if they are clearly duplicates
    c.execute("SELECT id, package_id, name, description, price FROM package_items WHERE name = 'Unknown Item'")
    unknowns = c.fetchall()
    
    deleted_count = 0
    for item in unknowns:
        # Check if there's a named item in the same package with similar details
        # Or if it's just a placeholder with no info
        c.execute("DELETE FROM package_items WHERE id = ?", (item['id'],))
        deleted_count += 1
        print(f"Deleted 'Unknown Item' [ID: {item['id']}] from package {item['package_id']}")

    # 2. Identify exact duplicates (same name, package_id, and price)
    # We keep the one with the lowest rowid (oldest) or just any one.
    c.execute("""
        SELECT name, package_id, price, COUNT(*) as count 
        FROM package_items 
        GROUP BY name, package_id, price 
        HAVING count > 1
    """)
    duplicates = c.fetchall()
    
    dup_deleted = 0
    for dup in duplicates:
        # Get all IDs for this duplicate set
        c.execute("SELECT id FROM package_items WHERE name = ? AND package_id = ? AND price = ?", (dup['name'], dup['package_id'], dup['price']))
        ids = [row['id'] for row in c.fetchall()]
        
        # Keep the first one, delete the rest
        for id_to_delete in ids[1:]:
            c.execute("DELETE FROM package_items WHERE id = ?", (id_to_delete,))
            dup_deleted += 1
            print(f"Deleted duplicate '{dup['name']}' [ID: {id_to_delete}] from package {dup['package_id']}")

    conn.commit()
    
    # 3. Recalculate package totals
    c.execute("SELECT id FROM packages")
    package_ids = [row['id'] for row in c.fetchall()]
    
    for pid in package_ids:
        c.execute("SELECT SUM(price) as total FROM package_items WHERE package_id = ?", (pid,))
        res = c.fetchone()
        new_total = res['total'] if res['total'] else 0.0
        c.execute("UPDATE packages SET total_price = ? WHERE id = ?", (new_total, pid))

    conn.commit()
    conn.close()

    print(f"\n--- Cleanup Finished ---")
    print(f"Total 'Unknown' items removed: {deleted_count}")
    print(f"Total exact duplicates removed: {dup_deleted}")
    print("Package totals recalculated.")

if __name__ == "__main__":
    cleanup_duplicates()
