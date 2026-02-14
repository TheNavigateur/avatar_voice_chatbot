import os
import requests
import json
import base64

# Load env from secrets.sh manually if needed, or assume running with `source secrets.sh`
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
    print("Error: Env vars not set.")
    exit(1)

credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

# Endpoint for Amazon Merchant (Standard Task)
url = "https://api.dataforseo.com/v3/merchant/amazon/products/task_post"

payload = [{
    "keyword": "hiking boots",
    "se_domain": "amazon.com"
}]

print(f"Sending request to {url}...")
try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    data = response.json()
    
    # Save raw output for inspection
    with open("amazon_debug_output.json", "w") as f:
        json.dump(data, f, indent=2)
        
    if data.get("status_code") == 20000:
        print("Success!")
        tasks = data.get("tasks", [])
        if tasks:
            items = tasks[0].get("result", [])[0].get("items", [])
            print(f"Found {len(items)} items.")
            for item in items[:3]:
                print(f"- {item.get('title')} (ASIN: {item.get('asin')})")
                print(f"  Price: {item.get('price_value')}")
    else:
        print("API Error:", data.get("status_message"))
        
except Exception as e:
    print(f"Request failed: {e}")
