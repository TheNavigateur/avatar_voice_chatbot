import os
import requests
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class GooglePlacesService:
    """Service to fetch real traveler reviews from Google Places API"""
    
    def __init__(self):
        self.api_key = os.environ.get('GOOGLE_API_KEY')
        
    def get_place_reviews(self, name: str, location: str = "") -> Optional[Dict]:
        """
        Searches for a place by name/location and returns up to 5 of its top reviews
        along with a link to the Google Maps listing.
        Returns: Dict containing 'reviews' (list of dicts) and 'review_link' (str)
        """
        if not self.api_key:
            logger.warning("Google Places Service: GOOGLE_API_KEY is not set.")
            return None
            
        try:
            # Step 1: Find the Place ID using Text Search
            search_query = f"{name} {location}".strip()
            search_url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
            search_params = {
                "query": search_query,
                "key": self.api_key
            }
            
            search_res = requests.get(search_url, params=search_params, timeout=5)
            search_data = search_res.json()
            
            if search_res.status_code != 200 or search_data.get('status') != 'OK' or not search_data.get('results'):
                logger.warning(f"Google Places Service: Could not find place ID for '{search_query}'. Status: {search_data.get('status')}")
                return None
                
            place_id = search_data['results'][0]['place_id']
            
            # Step 2: Fetch Place Details (specifically reviews and url)
            details_url = "https://maps.googleapis.com/maps/api/place/details/json"
            details_params = {
                "place_id": place_id,
                "fields": "name,rating,reviews,url",
                "key": self.api_key,
                "reviews_sort": "most_relevant" # Try to get the most helpful text reviews
            }
            
            details_res = requests.get(details_url, params=details_params, timeout=5)
            details_data = details_res.json()
            
            if details_res.status_code != 200 or details_data.get('status') != 'OK':
                logger.warning(f"Google Places Service: Could not fetch details for place_id '{place_id}'. Status: {details_data.get('status')}")
                return None
                
            result = details_data.get('result', {})
            raw_reviews = result.get('reviews', [])
            
            # Format to match our frontend expectation: [{"text": "...", "rating": 5}]
            formatted_reviews = []
            for r in raw_reviews:
                text = r.get('text', '').strip()
                rating = r.get('rating')
                
                # Only include reviews that actually have text
                if text and rating:
                    # Truncate very long reviews to keep UI clean
                    if len(text) > 300:
                        text = text[:297] + "..."
                        
                    formatted_reviews.append({
                        "text": text,
                        "rating": rating,
                        "author": r.get('author_name', 'Google User') # Bonus feature for UI if we want to show it later
                    })
            
            # Fallback if no text reviews were found despite having the place
            if not formatted_reviews:
                return {"reviews": [], "review_link": result.get('url')}
                
            return {
                "reviews": formatted_reviews,
                "review_link": result.get('url')
            }
            
        except Exception as e:
            logger.error(f"Google Places Service Error for '{name}': {e}")
            return None
