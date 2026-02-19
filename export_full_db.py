import sqlite3
import json

def export_db():
    conn = sqlite3.connect("app.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM packages")
    packages = [dict(row) for row in c.fetchall()]
    
    c.execute("SELECT * FROM package_items")
    items = [dict(row) for row in c.fetchall()]
    
    data = {
        "packages": packages,
        "items": items
    }
    
    with open("full_db_export.json", "w") as f:
        json.dump(data, f, indent=2)
    
    print(f"Exported {len(packages)} packages and {len(items)} items to full_db_export.json")
    conn.close()

if __name__ == "__main__":
    export_db()
