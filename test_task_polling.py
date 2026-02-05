
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

def test_polling():
    print("--- TESTING TASK POLLING (FLIGHTS) ---")
    
    # 1. POST TASK
    post_url = f"{BASE_URL}/flights/task_post"
    payload = [{
        "location_code": 2840,
        "language_code": "en",
        "fly_from": "LHR",
        "fly_to": "JFK",
        "date_from": "2025-03-01",
        "currency": "GBP"
    }]
    
    print("Posting task...")
    start_time = time.time()
    resp = requests.post(post_url, headers=_get_auth_header(), json=payload)
    data = resp.json()
    
    if data['status_code'] != 20000:
        print(f"Error posting task: {data['status_message']}")
        return
        
    task_id = data['tasks'][0]['id']
    print(f"Task ID: {task_id}")
    
    # 2. POLL
    get_url = f"{BASE_URL}/flights/task_get/advanced/{task_id}"
    
    attempts = 0
    while attempts < 20:
        attempts += 1
        time.sleep(2) # Wait 2s
        
        print(f"Polling attempt {attempts}...")
        resp = requests.get(get_url, headers=_get_auth_header())
        data = resp.json()
        
        if data['status_code'] == 20000:
            result_count = data['tasks'][0]['result_count']
            print(f"SUCCESS! Found {result_count} results.")
            print(f"Total Time: {time.time() - start_time:.2f} seconds")
            
            # Print first flight price
            try:
                items = data['tasks'][0]['result'][0]['items']
                print(f"First Flight: {items[0]['price']['value']} {items[0]['price']['currency']}")
            except:
                print("Could not parse items.")
                
            return
        elif data['status_code'] == 40401: # Task not found (means invalid ID or system error for GET)?
            # Actually DataForSEO usually returns the task with status "Active" if valid but not done
            # Or maybe 40602 "Task is initializing"
            print(f"Status: {data['status_message']} ({data['status_code']})")
        else:
            print(f"Status: {data['status_message']} ({data['status_code']})")
            
    print("Timed out.")

if __name__ == "__main__":
    if not DATAFORSEO_LOGIN:
        print("Set creds first")
    else:
        test_polling()
