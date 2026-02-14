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

# 2. Brute Force GET
endpoints = [
    f"https://api.dataforseo.com/v3/merchant/amazon/products/task_get/{task_id}",
    f"https://api.dataforseo.com/v3/merchant/amazon/products/task_get/advanced/{task_id}",
    f"https://api.dataforseo.com/v3/merchant/amazon/asin/task_get/{task_id}",
    f"https://api.dataforseo.com/v3/merchant/amazon/asin/task_get/advanced/{task_id}",
    f"https://api.dataforseo.com/v3/serp/amazon/organic/task_get/{task_id}",
    f"https://api.dataforseo.com/v3/serp/amazon/organic/task_get/advanced/{task_id}"
]

import time
print("Waiting 5s for task processing...")
time.sleep(5)

for url in endpoints:
    print(f"Trying: {url} ...")
    try:
        res = requests.get(url, headers=headers)
        data = res.json()
        code = data.get("status_code")
        
        # Check internal task status
        tasks = data.get("tasks", [])
        if tasks:
            task_status = tasks[0].get("status_code")
            print(f"  -> API Status: {code}, Task Status: {task_status}")
            
            if task_status == 20000:
                print("  🎉 REAL SUCCESS! Valid Data Found.")
                print(f"  Endpoint: {url}")
                with open("amazon_real_success.json", "w") as f:
                    json.dump(data, f, indent=2)
                break
            else:
                print(f"  -> Task Error: {tasks[0].get('status_message')}")
        else:
             print(f"  -> No tasks in response.")
            
    except Exception as e:
        print(f"  -> Exception: {e}")
