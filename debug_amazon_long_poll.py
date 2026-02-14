import os
import requests
import json
import base64
import time

# Load env
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# 1. Create FRESH Task
post_url = "https://api.dataforseo.com/v3/merchant/amazon/products/task_post"
payload = [{
    "keyword": "hiking boots",
    "se_domain": "amazon.com",
    "depth": 5
}]
print(f"Creating FRESH task at {post_url}...")
res = requests.post(post_url, headers=headers, json=payload)
data = res.json()
if data.get("status_code") != 20000:
    print(f"POST Failed: {data.get('status_message')}")
    exit(1)
task_id = data.get("tasks", [])[0].get("id")
print(f"Fresh Task ID: {task_id}")

# 2. Long Poll
get_url = f"https://api.dataforseo.com/v3/merchant/amazon/products/task_get/{task_id}"
print(f"Polling {get_url} for 60 seconds...")

for i in range(12): # 12 * 5s = 60s
    time.sleep(5)
    print(f"Attempt {i+1}/12...")
    try:
        res = requests.get(get_url, headers=headers)
        data = res.json()
        
        tasks = data.get("tasks")
        if tasks:
            status_code = tasks[0].get("status_code")
            print(f"  -> Task Status: {status_code}")
            
            if status_code == 20000:
                print("  🎉 SUCCESS! processing complete.")
                # Print key fields
                result = tasks[0].get("result")
                if result:
                    print("  Result Items Found.")
                    items = result[0].get("items", [])
                    print(f"  Count: {len(items)}")
                    for item in items[:2]:
                         print(f"  - Title: {item.get('title')}")
                         print(f"    Price: {item.get('price_value')}")
                         print(f"    Stock: {item.get('is_available')}") # Check field
                else:
                    print("  Result is empty.")
                break
            else:
                 print(f"  -> Msg: {tasks[0].get('status_message')}")
        else:
             print("  -> No tasks in response (Still processing or invalid standard EP).")
            
    except Exception as e:
        print(f"  -> Error: {e}")
