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

# Endpoint: DataForSEO Labs Amazon Live
url = "https://api.dataforseo.com/v3/dataforseo_labs/amazon/ranked_keywords/live"

payload = [{
    "asin": "B07P9W42B9", # Example ASIN (Nike shoes or similar generic)
    "location_code": 2840,
    "language_code": "en",
    "limit": 3
}]

print(f"Sending LIVE request to {url}...")
try:
    response = requests.post(url, headers=headers, json=payload)
    data = response.json()
    
    status_code = data.get("status_code")
    print(f"Status Code: {status_code}")
    
    if status_code == 20000:
        print("🎉 SUCCESS! Labs API works.")
        # Check results
        results = data.get("tasks", [])[0].get("result", [])
        print(f"Result Count: {len(results)}")
        # Dump for inspection
        with open("amazon_labs_success.json", "w") as f:
            json.dump(data, f, indent=2)
    else:
        print(f"API Error: {data.get('status_message')}")
        
except Exception as e:
    print(f"Request failed: {e}")
