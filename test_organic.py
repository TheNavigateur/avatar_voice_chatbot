
import os
import requests
import json
import base64

DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
BASE_URL = "https://api.dataforseo.com/v3/serp/google"

def _get_auth_header():
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def test_organic():
    print("--- TESTING ORGANIC LIVE ---")
    endpoint = f"{BASE_URL}/organic/live/advanced"
    
    payload = [{
        "keyword": "flights from London to New York",
        "location_code": 2840,
        "language_code": "en"
    }]
    
    resp = requests.post(endpoint, headers=_get_auth_header(), json=payload)
    data = resp.json()
    
    print(f"Status: {data.get('status_message')}")
    
    if data['status_code'] == 20000:
        items = data['tasks'][0]['result'][0]['items']
        print(f"Found {len(items)} organic items.")
        for item in items[:3]:
            print(f"- {item.get('type')}: {item.get('title')} ({item.get('url')})")

if __name__ == "__main__":
    test_organic()
