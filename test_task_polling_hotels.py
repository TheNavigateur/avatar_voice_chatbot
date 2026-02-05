
import os
import requests
import json
import base64
import time

DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")
BASE_URL = "https://api.dataforseo.com/v3/serp/google"

def _get_auth_header():
    credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

def test_polling_hotels():
    print("--- TESTING TASK POLLING (HOTELS) ---")
    
    # 1. POST TASK
    post_url = f"{BASE_URL}/hotels/task_post"
    payload = [{
        "location_name": "London, United Kingdom",
        "check_in": "2025-06-01",
        "check_out": "2025-06-02",
        "language_code": "en",
        "currency": "GBP",
        "sort_by": "highest_rating"
    }]
    
    print("Posting task...")
    start_time = time.time()
    resp = requests.post(post_url, headers=_get_auth_header(), json=payload)
    data = resp.json()
    
    if data['status_code'] != 20000:
        print(f"Error posting: {data.get('status_message')}")
        print(json.dumps(data, indent=2))
        return
        
    task_id = data['tasks'][0]['id']
    print(f"Task ID: {task_id}")
    
    # 2. POLL
    get_url = f"{BASE_URL}/hotels/task_get/advanced/{task_id}"
    
    attempts = 0
    while attempts < 20:
        attempts += 1
        time.sleep(2)
        
        print(f"Polling attempt {attempts}...")
        resp = requests.get(get_url, headers=_get_auth_header())
        data = resp.json()
        
        if data['status_code'] == 20000:
            result_count = data['tasks'][0]['result_count']
            print(f"SUCCESS! Found {result_count} results.")
            print(f"Total Time: {time.time() - start_time:.2f} seconds")
            
            if result_count > 0:
                try:
                    items = data['tasks'][0]['result'][0]['items']
                    print(f"First Hotel: {items[0]['title']} - Price: {items[0].get('price', {}).get('value')}")
                except Exception as e:
                    print(f"Parsing error: {e}")
            return
        else:
            print(f"Status: {data.get('status_message')}")
            
    print("Timed out.")

if __name__ == "__main__":
    test_polling_hotels()
