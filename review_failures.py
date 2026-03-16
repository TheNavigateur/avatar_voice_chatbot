import logging
from database import get_db_connection
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def review_tool_failures(limit: int = 10):
    """
    Summarizes the most recent tool failures recorded in the database.
    """
    print(f"\n{'='*80}")
    print(f"{'MOST RECENT TOOL FAILURES':^80}")
    print(f"{'='*80}\n")
    
    try:
        conn = get_db_connection()
        c = conn.cursor()
        
        # Note: We use rowid for ordering since we don't have a created_at timestamp in the schema yet
        # But we can see the IDs and types.
        c.execute("""
            SELECT tool_name, input_params, error_message, package_id 
            FROM tool_failures 
            ORDER BY rowid DESC 
            LIMIT ?
        """, (limit,))
        
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            print("No tool failures found in the database. Everything is running smoothly!")
            return

        for i, row in enumerate(rows, 1):
            print(f"[{i}] TOOL: {row['tool_name']}")
            print(f"    - ERROR: {row['error_message']}")
            print(f"    - PACKAGE: {row['package_id'] or 'None'}")
            
            try:
                params = json.loads(row['input_params'])
                print(f"    - INPUTS: {json.dumps(params, indent=8)}")
            except:
                print(f"    - INPUTS: {row['input_params']}")
            
            print(f"{'-'*80}")

    except Exception as e:
        logger.error(f"Failed to query tool failures: {e}")

if __name__ == "__main__":
    import sys
    limit = 10
    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except:
            pass
    review_tool_failures(limit)
