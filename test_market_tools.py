
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

def test_endpoint(suffix, name):
    print(f"\n--- TESTING {name} ---")
    endpoint = f"{BASE_URL}/{suffix}"
    
    payload = [{
        "location_code": 2840,
        "language_code": "en",
        "fly_from": "LHR",
        "fly_to": "JFK",
        "date_from": "2026-03-01"
    }]
    
    # Adjust payload for non-flights
    if "flights" not in suffix:
        payload = [{"keyword": "iphone 15", "location_code": 2840, "language_code": "en"}]

    try:
        response = requests.post(endpoint, headers=_get_auth_header(), json=payload)
        print(f"Endpoint: {suffix} -> Status: {response.status_code}")
        data = response.json()
        if data.get("tasks") and data["tasks"][0].get("status_message"):
            print(f"Msg: {data['tasks'][0]['status_message']}")
        else:
             print(f"Msg: {data.get('status_message')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_endpoint("flights/live/advanced", "Flights Live Advanced")
    test_endpoint("flights/live", "Flights Live (Standard)")
    test_endpoint("organic/live/advanced", "Organic Live Advanced (Control)")
    test_endpoint("hotels/live/advanced", "Hotels Live Advanced")
