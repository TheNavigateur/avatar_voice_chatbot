import os
import requests
import base64
import json

DATAFORSEO_LOGIN = os.environ.get("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.environ.get("DATAFORSEO_PASSWORD")

if not DATAFORSEO_LOGIN or not DATAFORSEO_PASSWORD:
    print("Error: Credentials not found.")
    exit(1)

credentials = f"{DATAFORSEO_LOGIN}:{DATAFORSEO_PASSWORD}"
token = base64.b64encode(credentials.encode()).decode()
headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}

url = "https://api.dataforseo.com/v3/serp/google/locations"

try:
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        tasks = data.get("tasks", [])
        if tasks:
            result = tasks[0].get("result", [])
            # Search for India
            for loc in result:
                if loc.get("location_name") == "India":
                    print(f"Found India: {loc}")
                if loc.get("location_name") == "United Kingdom":
                    print(f"Found UK: {loc}")
                if loc.get("location_name") == "United States":
                    print(f"Found US: {loc}")
                if loc.get("location_name") == "Canada":
                    print(f"Found CA: {loc}")
                if loc.get("location_name") == "Australia":
                    print(f"Found AU: {loc}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Exception: {e}")
