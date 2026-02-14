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

# Endpoint: Google SERP Live
url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"

# Query: specific item + "amazon" to trigger Amazon seller in Shopping Graph
payload = [{
    "keyword": "hiking boots size 10 amazon",
    "location_code": 2840,
    "language_code": "en",
    "depth": 50
}]

print(f"Sending request to {url}...")
try:
    res = requests.post(url, headers=headers, json=payload)
    data = res.json()
    
    if data.get("status_code") == 20000:
        print("🎉 Success!")
        
        # Save JSON
        with open("google_organic_debug.json", "w") as f:
            json.dump(data, f, indent=2)
            
        # Inspect for Shopping/Knowledge Graph
        results = data.get("tasks", [])[0].get("result", [])[0].get("items", [])
        print(f"Found {len(results)} items in SERP.")
        
        for item in results:
            item_type = item.get("type")
            if item_type in ["shopping", "paid", "knowledge_graph"]:
                print(f"Found Special Block: {item_type}")
                print(json.dumps(item, indent=2))
        
    else:
        print(f"Error: {data.get('status_message')}")

except Exception as e:
    print(f"Error: {e}")
