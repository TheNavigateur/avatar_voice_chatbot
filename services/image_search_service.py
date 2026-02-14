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
    
    def search_pexels(self, query: str, num: int = 1) -> list:
        """Search Pexels for an image"""
        if not self.pexels_api_key:
            return []
        
        try:
            url = "https://api.pexels.com/v1/search"
            headers = {"Authorization": self.pexels_api_key}
            params = {
                "query": query,
                "per_page": num,
                "orientation": "landscape"
            }
            
            response = requests.get(url, headers=headers, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('photos'):
                    return [p['src']['large'] for p in data['photos']]
        except Exception as e:
            logger.error(f"Pexels search failed: {e}")
        
        return []
    
    def search_pixabay(self, query: str, num: int = 1) -> list:
        """Search Pixabay for an image"""
        if not self.pixabay_api_key:
            return []
        
        try:
            url = "https://pixabay.com/api/"
            params = {
                "key": self.pixabay_api_key,
                "q": query,
                "image_type": "photo",
                "orientation": "horizontal",
                "per_page": max(3, num) # Pixabay min per_page is 3
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('hits'):
                    return [hit['largeImageURL'] for hit in data['hits'][:num]]
        except Exception as e:
            logger.error(f"Pixabay search failed: {e}")
        
        return []
    
    def search_google_images(self, query: str, num: int = 1) -> list:
        """Search Google Custom Search for an image"""
        if not self.google_api_key or not self.google_cx:
            return []
        
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": self.google_api_key,
                "cx": self.google_cx,
                "q": query,
                "searchType": "image",
                "num": num,
                "imgSize": "large"
            }
            
            response = requests.get(url, params=params, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('items'):
                    return [item['link'] for item in data['items']]
        except Exception as e:
            logger.error(f"Google Image search failed: {e}")
        
        return []
    
    def search_wikimedia(self, query: str, num: int = 1) -> list:
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
                "srlimit": num
            }
            
            response = requests.get(search_url, params=search_params, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                search_results = data.get('query', {}).get('search', [])
                
                results = []
                for res in search_results:
                    # Get the actual image URL
                    image_params = {
                        "action": "query",
                        "format": "json",
                        "titles": res['title'],
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
                                results.append(imageinfo[0].get('thumburl') or imageinfo[0].get('url'))
                return results
        except Exception as e:
            logger.error(f"Wikimedia search failed: {e}")
        
        return []
    
    def search_image_multi(self, query: str, num: int = 3, prefer_google: bool = False, is_hotel: bool = False) -> list:
        """
        Search for multiple images using various sources.
        Returns a list of successful results up to 'num'.
        """
        logger.info(f"Searching for multiple images ({num}): {query}")
        
        # Sources to try
        sources = []
        if prefer_google:
            sources.append(('google', self.search_google_images))
            sources.append(('pixabay', self.search_pixabay))
            sources.append(('pexels', self.search_pexels))
            sources.append(('wikimedia', self.search_wikimedia))
        elif is_hotel:
            sources.append(('pixabay', self.search_pixabay))
            sources.append(('google', self.search_google_images))
            sources.append(('pexels', self.search_pexels))
            sources.append(('wikimedia', self.search_wikimedia))
        else:
            sources.append(('wikimedia', self.search_wikimedia))
            sources.append(('pixabay', self.search_pixabay))
            sources.append(('pexels', self.search_pexels))
            sources.append(('google', self.search_google_images))

        results = []
        unreliable_domains = ['getyourguide.com', 'tripadvisor.com', 'viator.com', 'booking.com']
        bad_patterns = [
            '.pdf', '.svg', 'ia_sunrise', 'ebbflow', 'book cover', 
            'geograph.org.uk', 'larne', 'placeholder', 'no-image'
        ]

        for source_name, search_func in sources:
            if len(results) >= num:
                break
                
            # Request a few more than needed to allow for filtering
            found = search_func(query, num=max(10, num))
            
            for img_url in found:
                if img_url in results:
                    continue
                
                lower_url = img_url.lower()
                
                # Filter unreliable domains
                if any(domain in lower_url for domain in unreliable_domains):
                    continue
                
                # Filter out generic bad patterns
                if any(pattern in lower_url for pattern in bad_patterns):
                    continue
                    
                # Specific check for Wikimedia returning generic station images for "Arrival"
                if source_name == 'wikimedia' and 'station' in lower_url and 'arrival' in query.lower():
                    continue
                
                results.append(img_url)
                if len(results) >= num:
                    break
        
        return results

    def search_image(self, query: str, prefer_google: bool = False, is_hotel: bool = False) -> str:
        """
        Search for a single image using multiple sources.
        """
        images = self.search_image_multi(query, num=1, prefer_google=prefer_google, is_hotel=is_hotel)
        return images[0] if images else None
    
    def get_activity_image(self, activity_name: str, location: str = None, num: int = 1) -> list:
        """Get an image for an activity, optionally with location context"""
        query = activity_name
        if location:
            query = f"{activity_name} {location}"
        
        # Specialized handling for Arrival/Transfer items which often return bad results
        if any(word in activity_name.lower() for word in ['arrival', 'transfer', 'transport']):
            # Try specific first, but with 'airport' tag
            res = self.search_image_multi(f"{query} airport", num=num, prefer_google=True)
            if res: return res
            # Fallback to generic airport/travel image
            return self.search_image_multi("modern airport terminal", num=num, prefer_google=False)
        
        # Use Google FIRST for activities - gives most specific, promotional-quality results
        return self.search_image_multi(query, num=num, prefer_google=True)
    
    def get_hotel_image(self, hotel_name: str, num: int = 1) -> list:
        """Get an image for a hotel, prioritizing room photos"""
        # Improved query for hotels
        return self.search_image_multi(f"{hotel_name} hotel accommodation room", num=num, prefer_google=True, is_hotel=True)
    
    def get_flight_image(self, airline: str = None, num: int = 1) -> list:
        """Get an image for a flight/airline"""
        query = f"{airline} airline airplane flight" if airline else "commercial airplane flight"
        # Avoid Wikimedia for flights as it returns SVG logos
        return self.search_image_multi(query, num=num, prefer_google=False)
