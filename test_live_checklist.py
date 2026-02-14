import requests
import json

# Test the live server
url = "http://localhost:8001/chat"

# First, create a booked holiday by simulating the booking
# For now, let's just test if the agent responds with the checklist

payload = {
    "message": "Hi",
    "region": "UK"
}

print("Sending: Hi")
response = requests.post(url, json=payload)
data = response.json()
print(f"Agent: {data['response']}\n")
session_id = data.get('session_id')

# Accept shopping
payload2 = {
    "message": "Yes, show me the items",
    "session_id": session_id,
    "region": "UK"
}

print("Sending: Yes, show me the items")
response2 = requests.post(url, json=payload2)
data2 = response2.json()
print(f"Agent: {data2['response']}\n")

# Check if checklist is present
if '[SHOPPING_CHECKLIST]' in data2['response']:
    print("✅ SUCCESS: Checklist block found in response!")
else:
    print("❌ ISSUE: No checklist block in response")
    print("This might mean:")
    print("1. No booked holiday exists for this user")
    print("2. Agent didn't trigger the shopping flow")
