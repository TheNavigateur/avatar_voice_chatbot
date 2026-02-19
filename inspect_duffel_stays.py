from services.duffel_service import DuffelService
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

def inspect_duffel():
    duffel = DuffelService()
    print("Inspecting Duffel Client...")
    print(dir(duffel.client))
    
    if hasattr(duffel.client, 'stays'):
        print("\nFound 'stays' attribute!")
        print(dir(duffel.client.stays))
    else:
        print("\n'stays' attribute NOT found.")

if __name__ == "__main__":
    inspect_duffel()
