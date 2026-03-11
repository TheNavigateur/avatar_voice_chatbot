import os
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class GooglePlacesService:
    """Service to fetch real traveler reviews from Google Places API"""
    
    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_API_KEY')
        
    def get_place_data(self, name: str, location: str = "") -> Optional[Dict]:
        """
        Searches for a place by name/location and returns:
        - top reviews
        - official map photos
        - Google Maps listing link
        """
        if not self.api_key:
            logger.warning("Google Places Service: GOOGLE_API_KEY is not set.")
            return None
            
        try:
            # Step 1: Find the Place ID
            search_query = f"{name} {location}".strip()
            search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            search_params = {"query": search_query, "key": self.api_key}
            
            search_res = requests.get(search_url, params=search_params, timeout=5)
            search_data = search_res.json()
            
            if search_res.status_code != 200 or search_data.get('status') != 'OK' or not search_data.get('results'):
                return None
                
            place_id = search_data['results'][0]['place_id']
            
            # Step 2: Fetch Details including photos
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,rating,reviews,url,photos",
                "key": self.api_key
            }
            
            details_res = requests.get(details_url, params=details_params, timeout=5)
            details_data = details_res.json()
            
            if details_res.status_code != 200 or details_data.get('status') != 'OK':
                return None
                
            result = details_data.get('result', {})
            
            # 1. Process Reviews
            raw_reviews = result.get('reviews', [])
            formatted_reviews = []
            for r in raw_reviews:
                text = r.get('text', '').strip()
                if text and r.get('rating'):
                    formatted_reviews.append({
                        "text": text[:300] + ("..." if len(text) > 300 else ""),
                        "rating": r.get('rating'),
                        "author": r.get('author_name', 'Google User')
                    })
            
            # 2. Process Photos
            raw_photos = result.get('photos', [])
            photo_urls = []
            for p in raw_photos[:5]:
                ref = p.get('photo_reference')
                if ref:
                    # SECURE: Return a proxy URL instead of exposing the API Key in the URL
                    url = f"/api/proxy/photo?ref={ref}"
                    photo_urls.append(url)
            
            return {
                "reviews": formatted_reviews,
                "review_link": result.get('url'),
                "photos": photo_urls,
                "coordinates": result.get('geometry', {}).get('location')
            }
        except Exception as e:
            logger.error(f"Google Places Service Error for '{name}': {e}")
            return None

    def get_coordinates(self, location_name: str) -> Optional[Dict[str, float]]:
        """Resolves a location name to coordinates using Google Places Text Search."""
        if not self.api_key: return None
        try:
            url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            params = {"query": location_name, "key": self.api_key}
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            if data.get('status') == 'OK' and data.get('results'):
                loc = data['results'][0].get('geometry', {}).get('location')
                if loc:
                    return {"lat": loc['lat'], "lng": loc['lng']}
        except Exception as e:
            logger.error(f"Google Places Geocoding Error for '{location_name}': {e}")
        return None

    def get_place_reviews(self, name: str, location: str = "") -> Optional[Dict]:
        data = self.get_place_data(name, location)
        if data:
            return {"reviews": data['reviews'], "review_link": data['review_link']}
        return None
