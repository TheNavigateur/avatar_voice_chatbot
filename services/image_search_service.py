import os
import requests
import logging

logger = logging.getLogger(__name__)

class ImageSearchService:
    """Service to search for relevant images for activities, hotels, and flights"""
    
    def __init__(self):
        # Pexels API (free, 200 requests/hour)
        self.pexels_api_key = os.environ.get('PEXELS_API_KEY')
        
        # Pixabay API (free, good quality)
        self.pixabay_api_key = os.environ.get('PIXABAY_API_KEY')
        
        # Google Custom Search (100 free queries/day, but most accurate)
        self.google_api_key = os.environ.get('GOOGLE_API_KEY')
        self.google_cx = os.environ.get('GOOGLE_CSE_ID')  # Use existing CSE ID
    
    def search_pexels(self, query: str) -> str:
        """Search Pexels for an image"""
        if not self.pexels_api_key:
            return None
        
        try:
            url = "https://api.pexels.com/v1/search"
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": query,
                "per_page": 1,
                "orientation": "landscape"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos'):
                    return data['photos'][0]['src']['large']
        except Exception as e:
            logger.error(f"Pexels search failed: {e}")
        
        return None
    
    def search_pixabay(self, query: str) -> str:
        """Search Pixabay for an image"""
        if not self.pixabay_api_key:
            return None
        
        try:
            url = "https://pixabay.com/api/"
            params = {
                "key": self.pixabay_api_key,
                "q": query,
                "image_type": "photo",
                "orientation": "horizontal",
                "per_page": 3
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('hits'):
                    return data['hits'][0]['largeImageURL']
        except Exception as e:
            logger.error(f"Pixabay search failed: {e}")
        
        return None
    
    def search_google_images(self, query: str) -> str:
        """Search Google Custom Search for an image"""
        if not self.google_api_key or not self.google_cx:
            return None
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx,
                "q": query,
                "searchType": "image",
                "num": 1,
                "imgSize": "large"
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    return data['items'][0]['link']
        except Exception as e:
            logger.error(f"Google Image search failed: {e}")
        
        return None
    
    def search_wikimedia(self, query: str) -> str:
        """Search Wikimedia Commons for an image"""
        try:
            # Use Wikimedia Commons API to search for images
            search_url = "https://commons.wikimedia.org/w/api.php"
            
            # Wikimedia requires a User-Agent header
            headers = {
                "User-Agent": "TravelBot/1.0 (https://github.com/yourapp; contact@yourapp.com)"
            }
            
            # First, search for the page
            search_params = {
                "action": "query",
                "format": "json",
                "list": "search",
                "srsearch": query,
                "srnamespace": "6",  # File namespace
                "srlimit": "3"
            }
            
            response = requests.get(search_url, params=search_params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('query', {}).get('search', [])
                
                if search_results:
                    # Get the first result's title
                    file_title = search_results[0]['title']
                    
                    # Get the actual image URL
                    image_params = {
                        "action": "query",
                        "format": "json",
                        "titles": file_title,
                        "prop": "imageinfo",
                        "iiprop": "url",
                        "iiurlwidth": "1280"
                    }
                    
                    img_response = requests.get(search_url, params=image_params, headers=headers, timeout=5)
                    
                    if img_response.status_code == 200:
                        img_data = img_response.json()
                        pages = img_data.get('query', {}).get('pages', {})
                        
                        for page in pages.values():
                            imageinfo = page.get('imageinfo', [])
                            if imageinfo:
                                # Return the thumbnail URL (or original if no thumbnail)
                                return imageinfo[0].get('thumburl') or imageinfo[0].get('url')
        except Exception as e:
            logger.error(f"Wikimedia search failed: {e}")
        
        return None
    
    def search_image(self, query: str, prefer_google: bool = False) -> str:
        """
        Search for an image using multiple sources.
        Returns the first successful result.
        
        Args:
            query: Search query
            prefer_google: If True, try Google first (best for specific places/activities)
        """
        logger.info(f"Searching for image: {query} (prefer_google={prefer_google})")
        
        # For specific activities/places, try Wikimedia first (verified, specific photos)
        if prefer_google:  # Reuse this flag for "prefer specific sources"
            image_url = self.search_wikimedia(query)
            if image_url:
                logger.info(f"Found image via Wikimedia: {query}")
                return image_url
        
        # Try Pixabay (free, 5000/hour - most generous)
        image_url = self.search_pixabay(query)
        if image_url:
            logger.info(f"Found image via Pixabay: {query}")
            return image_url
        
        # Try Pexels (free, 200/hour)
        image_url = self.search_pexels(query)
        if image_url:
            logger.info(f"Found image via Pexels: {query}")
            return image_url
        
        # Try Wikimedia as fallback if not already tried
        if not prefer_google:
            image_url = self.search_wikimedia(query)
            if image_url:
                logger.info(f"Found image via Wikimedia: {query}")
                return image_url
        
        # Try Google as last resort
        image_url = self.search_google_images(query)
        if image_url:
            logger.info(f"Found image via Google: {query}")
            return image_url
        
        logger.warning(f"No image found for: {query}")
        return None
    
    def get_activity_image(self, activity_name: str, location: str = None) -> str:
        """Get an image for an activity, optionally with location context"""
        query = activity_name
        if location:
            query = f"{activity_name} {location}"
        
        # Use Google FIRST for activities - gives most specific, promotional-quality results
        return self.search_image(query, prefer_google=True)
    
    def get_hotel_image(self, hotel_name: str) -> str:
        """Get an image for a hotel, prioritizing room photos"""
        return self.search_image(f"{hotel_name} room", prefer_google=True)
    
    def get_flight_image(self, airline: str = None) -> str:
        """Get an image for a flight/airline"""
        query = f"{airline} airplane" if airline else "airplane flight"
        return self.search_image(query)
