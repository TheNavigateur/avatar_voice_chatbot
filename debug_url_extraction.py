
import os
import requests
import json
import base64

# Credentials
DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

query = "Nike Running Shoes Size 10 Amazon"
url = "https://api.dataforseo.com/v3/serp/google/organic/live/advanced"
payload = [{
    "keyword": query,
    "location_code": 2840,
    "language_code": "en",
    "depth": 50
}]

print(f"Querying: {query}...")
try:
    res = requests.post(url, headers=headers, json=payload)
    data = res.json()
    
    tasks = data.get("tasks", [])
    if not tasks: exit("No tasks")
    
    results = tasks[0].get("result", [])[0].get("items", [])
    
    print(f"Found {len(results)} items.")
    
    print(f"Scanning {len(results)} items for Amazon Product Links...")
    
    for item in results:
        url = item.get("url") or item.get("link")
        if not url: continue
        
        if "amazon" in url:
            if "/dp/" in url or "/gp/product/" in url:
                print(f"[PRODUCT] {url}")
            elif "/s?k=" in url or "/b?" in url:
                print(f"[SEARCH] {url}")
            else:
                print(f"[OTHER] {url}")

except Exception as e:
    print(e)
