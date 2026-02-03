
import os
import asyncio
from google.genai import Client

async def list_models():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("GOOGLE_API_KEY not set")
        return

    client = Client(api_key=api_key)
    
    print("Listing models...")
    try:
        # Paged iteration might be needed, but let's try basic list first
        # The library seems to be 'google-genai'
        async for model in await client.aio.models.list(config={"page_size": 50}):
             print(f"Model: {model.name}")
             # print(f"  Supported methods: {model.supported_generation_methods}")
             
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    # source secrets if needed, but we assume environment or secrets.sh sourced before running
    # actually better to load secrets here manually to be safe
    if os.path.exists("secrets.sh"):
        with open("secrets.sh") as f:
            for line in f:
                if line.startswith("export "):
                    key, value = line.strip().replace("export ", "").split("=", 1)
                    os.environ[key] = value.strip('"')

    asyncio.run(list_models())
