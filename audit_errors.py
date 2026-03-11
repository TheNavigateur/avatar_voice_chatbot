import json
import uuid
import sys
import logging
from typing import Dict, Any, List
from database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def list_recent_failures(limit: int = 10):
    """Lists the most recent tool failures from the Mistake Journal."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "SELECT id, timestamp, tool_name, input_params, error_message, status FROM tool_failures ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        failures = c.fetchall()
        conn.close()
        
        if not failures:
            print("\n✅ No recent tool failures found in the Journal.")
            return []
        
        print(f"\n📝 Recent Tool Failures ({len(failures)}):")
        print("-" * 100)
        for f in failures:
            print(f"ID: {f['id'][:8]}... | {f['timestamp']} | Tool: {f['tool_name']} | Status: {f['status']}")
            print(f"Params: {f['input_params'][:100]}...")
            print(f"Error:  {f['error_message']}")
            print("-" * 100)
        return failures
    except Exception as e:
        logger.error(f"Failed to list failures: {e}")
        return []

def add_correction_rule(pattern: str, replacement: str, tool_scope: str = None):
    """Adds a new correction rule to the Rulebook."""
    try:
        conn = get_db_connection()
        c = conn.cursor()
        rule_id = str(uuid.uuid4())
        c.execute(
            "INSERT INTO correction_rules (id, pattern, replacement, tool_scope) VALUES (?, ?, ?, ?)",
            (rule_id, pattern, replacement, tool_scope)
        )
        conn.commit()
        conn.close()
        print(f"\n✨ Added Correction Rule: '{pattern}' -> '{replacement}' (Scope: {tool_scope or 'Global'})")
    except Exception as e:
        logger.error(f"Failed to add correction rule: {e}")

def manual_patch_item(package_id: str, title: str, item_type: str, price: float, description: str):
    """Manually adds an item to a package (The Quick Fix)."""
    # This imports tools only when needed to avoid circular dependencies
    from agent_tools import add_item_to_package_tool
    try:
        res = add_item_to_package_tool("manual_patch", package_id, title, item_type, price, description)
        print(f"\n🛠️ Manual Patch applied: {res}")
    except Exception as e:
        logger.error(f"Failed to apply manual patch: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        list_recent_failures()
        print("\nUsage:")
        print("  python audit_errors.py list                  # List failures")
        print("  python audit_errors.py fix <pattern> <repl>  # Add a rule")
        print("  python audit_errors.py patch <pkg_id> <title> <type> <price> <desc>")
    else:
        cmd = sys.argv[1]
        if cmd == "list":
            list_recent_failures()
        elif cmd == "fix" and len(sys.argv) >= 4:
            add_correction_rule(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
        elif cmd == "patch" and len(sys.argv) >= 7:
            manual_patch_item(sys.argv[2], sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6])
