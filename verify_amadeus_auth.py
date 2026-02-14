import os
import sys
from amadeus import Client, ResponseError
import logging

# Need to reload logging to see debug
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger("amadeus")
logger.setLevel(logging.DEBUG)

def verify_auth():
    print("--- Verifying Amadeus Auth ---")
    client_id = os.environ.get("AMADEUS_CLIENT_ID")
    client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("ERROR: Credentials missing in env.")
        return

    print(f"Client ID: {client_id[:4]}...{client_id[-4:]}")
    
    try:
        amadeus = Client(
            client_id=client_id,
            client_secret=client_secret,
            log_level='debug' # Force SDK logging
        )
        
        # Simple test call
        print("Attempting to fetch access token (implicit)...")
        # Just validatng a simple location search
        response = amadeus.reference_data.locations.get(
            keyword='LON',
            subType='CITY'
        )
        print("Success!")
        print(response.data[0])
        
    except ResponseError as error:
        print(f"API Error: {error}")
        if error.response:
            print(f"Status: {error.response.status_code}")
            print(f"Body: {error.response.body}")
    except Exception as e:
        print(f"General Error: {e}")

if __name__ == "__main__":
    verify_auth()
