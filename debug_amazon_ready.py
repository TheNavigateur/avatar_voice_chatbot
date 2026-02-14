import os
import requests
import json
import base64

# Load env
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
    print("Error: Env vars not set.")
    exit(1)

credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# Check TASKS READY
# This endpoint lists all completed tasks and their Result URLs
url = "https://api.dataforseo.com/v3/merchant/amazon/products/tasks_ready"

print(f"Checking {url}...")
try:
    response = requests.get(url, headers=headers)
    data = response.json()
    
    # Save for inspection
    with open("amazon_ready_debug.json", "w") as f:
        json.dump(data, f, indent=2)
        
    if data.get("status_code") == 20000:
        tasks = data.get("tasks", [])
        print(f"Found {len(tasks)} ready tasks.")
        
        for task in tasks[:3]:
            # The Holy Grail: The API tells us exactly where to get the result
            print(f"Task ID: {task.get('id')}")
            print(f"Result URL: {task.get('result_url')}")
            
            # Let's try to fetch one if we find it
            if task.get('result_url'):
                print(f"Test Fetching result from: {task.get('result_url')}...")
                # The result_url is usually relative or absolute?
                # Usually it's like "/v3/..."
                # We need to prepend domain if it's relative
                # But typically 'result_url' in DataForSEO is just the string pattern? check json.
                pass
    else:
        print(f"API Error: {data.get('status_message')}")
        
except Exception as e:
    print(f"Request failed: {e}")
