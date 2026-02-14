import sqlite3
import json
import requests
import time

def search_image_serpapi(query):
    """Search for images using SerpAPI Google Images (free tier: 100 searches/month)"""
    api_key = "YOUR_SERPAPI_KEY"  # Get from serpapi.com
    
    try:
        url = "https://serpapi.com/search"
        params = {
            "engine": "google_images",
            "q": query,
            "api_key": api_key,
            "num": 1
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('images_results'):
                return data['images_results'][0]['original']
    except Exception as e:
        print(f"❌ SerpAPI search failed: {e}")
    
    return None

def search_image_duckduckgo(query):
    """Search for images using DuckDuckGo (free, no API key needed)"""
    try:
        from duckduckgo_search import DDGS
        
        with DDGS() as ddgs:
            results = list(ddgs.images(query, max_results=1))
            if results:
                return results[0]['image']
    except Exception as e:
        print(f"❌ DuckDuckGo search failed: {e}")
    
    return None

def search_image_pixabay(query):
    """Search for images using Pixabay (free API)"""
    api_key = "YOUR_PIXABAY_KEY"  # Get from pixabay.com/api/docs/
    
    try:
        url = "https://pixabay.com/api/"
        params = {
            "key": api_key,
            "q": query,
            "image_type": "photo",
            "per_page": 3
        }
        
        response = requests.get(url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('hits'):
                return data['hits'][0]['largeImageURL']
    except Exception as e:
        print(f"❌ Pixabay search failed: {e}")
    
    return None

def get_web_image(query):
    """Try multiple sources to get an image"""
    print(f"  🔍 Searching web for: {query}")
    
    # Try DuckDuckGo first (no API key needed)
    image_url = search_image_duckduckgo(query)
    if image_url:
        print(f"    ✓ Found via DuckDuckGo")
        return image_url
    
    # Try Pixabay
    image_url = search_image_pixabay(query)
    if image_url:
        print(f"    ✓ Found via Pixabay")
        return image_url
    
    # Fallback to generic images
    print(f"    ⚠️  Using fallback image")
    return "https://images.unsplash.com/photo-1469854523086-cc02fe5d8800?w=800"

def fix_missing_images():
    """Fix all items with missing or broken images"""
    conn = sqlite3.connect('app.db')
    c = conn.cursor()
    
    # Get all items
    items = c.execute('''
        SELECT id, name, item_type, metadata
        FROM package_items
    ''').fetchall()
    
    print(f"Checking {len(items)} items for missing images...\n")
    
    fixed = 0
    
    for item_id, name, item_type, metadata_str in items:
        metadata = json.loads(metadata_str) if metadata_str else {}
        
        # Check if image is missing or broken
        image_url = metadata.get('image_url')
        
        if not image_url:
            print(f"🔧 Fixing: {name}")
            
            # Get image from web
            search_query = name.replace('Travel to', '').replace('Airport', '').strip()
            new_image_url = get_web_image(search_query)
            
            if new_image_url:
                metadata['image_url'] = new_image_url
                
                c.execute('''
                    UPDATE package_items
                    SET metadata = ?
                    WHERE id = ?
                ''', (json.dumps(metadata), item_id))
                
                fixed += 1
                time.sleep(0.5)  # Rate limiting
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ Fixed {fixed} items")

if __name__ == '__main__':
    # First, install duckduckgo_search if needed
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        print("Installing duckduckgo_search...")
        import subprocess
        subprocess.run(['pip3', 'install', 'duckduckgo_search'], check=True)
    
    fix_missing_images()
