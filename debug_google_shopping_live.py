import os
import requests
import json
import base64

# Load env
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# Endpoint: Google Shopping Live
url = "https://api.dataforseo.com/v3/serp/google/shopping/live/advanced"

# Query: generic item
payload = [{
    "keyword": "hiking boots size 10",
    "location_code": 2840,
    "language_code": "en",
    "device": "desktop"
}]

print(f"Sending LIVE request to {url}...")
try:
    res = requests.post(url, headers=headers, json=payload)
    data = res.json()
    
    if data.get("status_code") == 20000:
        print("🎉 Success!")
        
        # Save JSON first!
        with open("shopping_live_debug.json", "w") as f:
            json.dump(data, f, indent=2)
            
        tasks = data.get("tasks", [])
        if not tasks:
            print("No tasks found.")
        elif not tasks[0].get("result"):
             print("No result found in task.")
        else:
            items = tasks[0].get("result", [])[0].get("items", [])
            print(f"Found {len(items)} items.")
            
            # Filter for Amazon
            amazon_items = []
            for item in items:
                source = (item.get("source") or "").lower()
                if "amazon" in source:
                    amazon_items.append(item)
                    
            print(f"Found {len(amazon_items)} Amazon items.")
        
        for item in amazon_items[:3]:
             print(f"- {item.get('title')}")
             print(f"  Price: {item.get('price_value')}")
             print(f"  Source: {item.get('source')}")
             print(f"  Delivery: {item.get('delivery_info')}")
             
             # Save one for inspection
             with open("shopping_live_success.json", "w") as f:
                 json.dump(items[0], f, indent=2)
                 
    else:
        print(f"Error: {data.get('status_message')}")

except Exception as e:
    print(f"Error: {e}")
