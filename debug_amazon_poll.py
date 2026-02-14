import os
import requests
import json
import base64
import time

# Load env
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
    print("Error: Env vars not set.")
    exit(1)

credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# 1. POST TASK
post_url = "https://api.dataforseo.com/v3/serp/amazon/organic/task_post"
payload = [{
    "keyword": "hiking boots",
    "location_code": 2840,
    "depth": 5
}]

print(f"POSTing task to {post_url}...")
try:
    response = requests.post(post_url, headers=headers, json=payload)
    data = response.json()
    
    if data.get("status_code") != 20000:
        print(f"POST Failed: {data.get('status_message')}")
        exit(1)
        
    task_id = data.get("tasks", [])[0].get("id")
    print(f"Task Created! ID: {task_id}")
    
except Exception as e:
    print(f"POST Request failed: {e}")
    exit(1)

# 2. POLL FOR RESULTS
get_url = f"https://api.dataforseo.com/v3/serp/amazon/organic/task_get/{task_id}"
print(f"Polling {get_url}...")

while True:
    time.sleep(3) # Wait 3s
    try:
        res = requests.get(get_url, headers=headers)
        res_data = res.json()
        
        if not res_data:
            print("Empty response")
            continue
            
        tasks = res_data.get("tasks")
        if not tasks:
            print(f"No tasks in response. Keys: {list(res_data.keys())}")
            # Check if it's a raw error
            if res_data.get("status_code") != 20000:
                print(f"API Error: {res_data.get('status_message')}")
            continue
            
        status_code = tasks[0].get("status_code")
        print(f"Status Code: {status_code}")
        
        if status_code == 20000:
            print("Task Completed!")
            # Save Full Output
            with open("amazon_stock_data.json", "w") as f:
                json.dump(res_data, f, indent=2)
            print("Saved to amazon_stock_data.json")
            
            # Print Summary
            items = res_data.get("tasks", [])[0].get("result", [])[0].get("items", [])
            print(f"Found {len(items)} items.")
            for item in items[:3]:
                print(f"- {item.get('title')}")
                print(f"  Price: {item.get('price_value')}")
                print(f"  Availability: {item.get('availability', 'N/A')}") # Check for this field!
                print(f"  Delivery: {item.get('delivery_info', 'N/A')}")
            break
            
        elif status_code == 40602:
            print("Still processing...")
        else:
            print(f"Task Failed: {res_data.get('tasks', [])[0].get('status_message')}")
            break
            
    except Exception as e:
        print(f"Polling failed: {e}")
        break
