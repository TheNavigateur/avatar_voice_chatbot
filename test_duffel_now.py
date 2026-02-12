import os
import sys
sys.path.insert(0, '/Users/naveenchawla/Repos/google_adk_voice_bot')

# Load secrets
import subprocess
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd='/Users/naveenchawla/Repos/google_adk_voice_bot')
for line in result.stdout.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value

from services.duffel_service import DuffelService
from datetime import datetime, timedelta

# Test flight search
duffel = DuffelService()

# Try a simple search
tomorrow = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
print(f"Testing flight search: LHR -> CDG on {tomorrow}")
print("-" * 60)

try:
    result = duffel.search_flights_formatted("LHR", "CDG", tomorrow)
    print(result)
    print("-" * 60)
    print("✅ Flight search working!")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
