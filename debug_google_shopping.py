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

# 1. POST TASK (Google Shopping)
post_url = "https://api.dataforseo.com/v3/serp/google/shopping/task_post"
payload = [{
    "keyword": "hiking boots size 10",
    "location_code": 2840,
    "language_code": "en",
    "device": "desktop"
}]

print(f"POSTing task to {post_url}...")
try:
    res = requests.post(post_url, headers=headers, json=payload)
    data = res.json()
    if data.get("status_code") != 20000:
        print(f"POST Failed: {data.get('status_message')}")
        exit(1)
    task_id = data.get("tasks", [])[0].get("id")
    print(f"Task ID: {task_id}")
    
    # 2. POLL
    get_url = f"https://api.dataforseo.com/v3/serp/google/shopping/task_get/{task_id}"
    print(f"Polling {get_url}...")
    
    for i in range(10):
        time.sleep(3)
        res = requests.get(get_url, headers=headers)
        data = res.json()
        tasks = data.get("tasks", [])
        
        if tasks and tasks[0].get("status_code") == 20000:
            print("🎉 Task Completed!")
            
            items = tasks[0].get("result", [])[0].get("items", [])
            print(f"Found {len(items)} items.")
            
            # Filter for Amazon
            amazon_items = [item for item in items if "amazon" in (item.get("source") or "").lower()]
            print(f"Found {len(amazon_items)} Amazon items.")
            
            for item in amazon_items[:3]:
                 print(f"- {item.get('title')}")
                 print(f"  Price: {item.get('price_value')}")
                 print(f"  Source: {item.get('source')}")
                 print(f"  Url: {item.get('product_url')}") # Deep link?
            
            # Save for inspection
            with open("google_shopping_test.json", "w") as f:
                json.dump(data, f, indent=2)
            break
        elif tasks and tasks[0].get("status_code") == 40602:
            print("Processing...")
        else:
            print("Waiting/Error...")
            
except Exception as e:
    print(f"Error: {e}")
