#!/usr/bin/env python3
"""Quick test of Pixabay image search"""
import sys
import os

# Load environment
import subprocess
result = subprocess.run(['bash', '-c', 'source secrets.sh && env'], capture_output=True, text=True, cwd='/Users/naveenchawla/Repos/google_adk_voice_bot')
for line in result.stdout.split('\n'):
    if '=' in line:
        key, value = line.split('=', 1)
        os.environ[key] = value

sys.path.insert(0, '/Users/naveenchawla/Repos/google_adk_voice_bot')

from services.image_search_service import ImageSearchService

# Test the service
service = ImageSearchService()

print("Testing Pixabay image search...\n")

test_queries = [
    "Playa del Duque beach Tenerife",
    "Eiffel Tower Paris",
    "Dubai Marina"
]

for query in test_queries:
    print(f"🔍 Searching: {query}")
    image_url = service.search_image(query)
    if image_url:
        print(f"   ✅ Found: {image_url[:80]}...")
    else:
        print(f"   ❌ Not found")
    print()
