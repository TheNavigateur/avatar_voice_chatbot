import requests
import json

def test_chat_stream():
    url = "http://localhost:8001/chat_stream"
    payload = {
        "message": "Hi, I'm going to London. What can I buy for the trip?",
        "region": "UK"
    }
    
    try:
        response = requests.post(url, json=payload, stream=True)
        print(f"Status: {response.status_code}")
        
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                print(f"Received: {decoded_line}")
                if "[DONE]" in decoded_line:
                    print("Stream finished.")
                    break
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chat_stream()
