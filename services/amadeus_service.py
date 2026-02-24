import os
import logging
from amadeus import Client, ResponseError
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class AmadeusService:
    def __init__(self):
        # Amadeus credentials
        self.client_id = os.environ.get("AMADEUS_CLIENT_ID")
        self.client_secret = os.environ.get("AMADEUS_CLIENT_SECRET")
        
        if not self.client_id or not self.client_secret:
            logger.warning("AMADEUS_CLIENT_ID or SECRET not set. Hotel Service disabled.")
            self.amadeus = None
        else:
            try:
                self.amadeus = Client(
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
            except Exception as e:
                logger.error(f"Failed to initialize Amadeus Client: {e}")
                self.amadeus = None

    def search_hotels_by_city(self, city_code: str) -> List[Dict]:
        """
        Search for hotels in a city (using IATA city/airport code like 'LON', 'PAR').
        Returns list of hotel offers.
        """
        if not self.amadeus: return []
        
        try:
            # 1. Get List of Hotels in City (Reference Data)
            # This endpoint returns hotel IDs for a city code
            logger.info(f"Searching Amadeus hotels in {city_code}...")
            
            hotels_response = self.amadeus.reference_data.locations.hotels.by_city.get(
                cityCode=city_code
            )
            
            if not hotels_response.data:
                return []
                
            # Get first 20 hotel IDs to check offers for
            hotel_ids = [h['hotelId'] for h in hotels_response.data[:20]]
            
            if not hotel_ids:
                return []
                
            # 2. Get Offers for specific hotels
            # Hotel Offers API (Multi-Hotel)
            logger.info(f"Checking offers for {len(hotel_ids)} hotels...")
            offers_response = self.amadeus.shopping.hotel_offers_search.get(
                hotelIds=','.join(hotel_ids),
                adults=1
            )
            
            if not offers_response.data:
                return []
                
            results = []
            for offer in offers_response.data:
                hotel = offer.get('hotel', {})
                name = hotel.get('name', 'Unknown Hotel')
                hotel_id = hotel.get('hotelId')
                
                # Offers list
                for offer_item in offer.get('offers', [])[:1]: # just take first offer per hotel
                    price_obj = offer_item.get('price', {})
                    currency = price_obj.get('currency', 'EUR')
                    amount = price_obj.get('total', '0.00')
                    offer_id = offer_item.get('id')
                    
                    results.append({
                        "name": name,
                        "price": f"{currency} {amount}",
                        "hotel_id": hotel_id,
                        "offer_id": offer_id,
                        "address": hotel.get('address', {}),
                        "latitude": hotel.get('latitude'),
                        "longitude": hotel.get('longitude'),
                        "details": f"{name} ({currency} {amount})"
                    })
                    
            return results

        except ResponseError as error:
            logger.error(f"Amadeus API Error: {error}")
            if error.response:
                logger.error(f"Response Body: {error.response.body}")
            return []
        except Exception as e:
            logger.error(f"Amadeus Service Error: {e}")
            return []

    def search_hotels_by_location(self, latitude: float, longitude: float, radius: int = 10) -> List[Dict]:
        """
        Search for hotels within a radius of given coordinates.
        """
        if not self.amadeus: return []
        
        try:
            logger.info(f"Searching Amadeus hotels near ({latitude}, {longitude}) radius={radius}km...")
            
            # 1. Search by Geocode
            hotels_response = self.amadeus.reference_data.locations.hotels.by_geocode.get(
                latitude=latitude,
                longitude=longitude,
                radius=radius,
                radiusUnit='KM'
            )
            
            if not hotels_response.data:
                return []
                
            hotel_ids = [h['hotelId'] for h in hotels_response.data[:20]]
            
            # 2. Get Offers
            offers_response = self.amadeus.shopping.hotel_offers_search.get(
                hotelIds=','.join(hotel_ids),
                adults=1
            )
            
            if not offers_response.data:
                return []
                
            results = []
            for offer in offers_response.data:
                hotel = offer.get('hotel', {})
                name = hotel.get('name', 'Unknown Hotel')
                hotel_id = hotel.get('hotelId')
                
                # Fetch distance if available - not directly in Multi-Hotel but sometimes in search results
                # For Multi-Hotel search, we'd need to cross-ref with the by_geocode response if we want distance
                dist = "N/A"
                for h_ref in hotels_response.data:
                    if h_ref['hotelId'] == hotel_id:
                        dist_val = h_ref.get('distance', {}).get('value')
                        dist_unit = h_ref.get('distance', {}).get('unit', 'KM')
                        if dist_val: dist = f"{dist_val} {dist_unit}"
                        break

                for offer_item in offer.get('offers', [])[:1]:
                    price_obj = offer_item.get('price', {})
                    currency = price_obj.get('currency', 'EUR')
                    amount = price_obj.get('total', '0.00')
                    offer_id = offer_item.get('id')
                    
                    results.append({
                        "name": name,
                        "price": f"{currency} {amount}",
                        "hotel_id": hotel_id,
                        "offer_id": offer_id,
                        "distance": dist,
                        "address": hotel.get('address', {}),
                        "latitude": hotel.get('latitude'),
                        "longitude": hotel.get('longitude'),
                        "details": f"{name} ({currency} {amount}) - {dist} away"
                    })
                    
            return results
        except Exception as e:
            logger.error(f"Amadeus Geo Hotel Search Error: {e}")
            return []

    def get_hotel_sentiments(self, hotel_ids: List[str]) -> Dict[str, Dict]:
        """
        Fetches itemized sentiments (ratings) for a list of hotel IDs.
        """
        if not self.amadeus or not hotel_ids: return {}
        
        try:
            logger.info(f"Fetching sentiments for {len(hotel_ids)} hotels...")
            response = self.amadeus.ereputation.hotel_sentiments.get(
                hotelIds=','.join(hotel_ids)
            )
            
            sentiments_by_id = {}
            if response.data:
                for item in response.data:
                    h_id = item.get('hotelId')
                    # Overall score and sub-scores
                    sentiments_by_id[h_id] = {
                        "overall": item.get('overallRating'),
                        "scores": item.get('sentiments', {})
                    }
            return sentiments_by_id
        except Exception as e:
            logger.warning(f"Failed to fetch sentiments: {e}")
            return {}

    def resolve_city_to_iata(self, place_name: str) -> Optional[str]:
        """
        Tries to find a City IATA code for a given place name.
        e.g. "Palma de Mallorca" -> "PMI"
        """
        if not self.amadeus: return None
        try:
            response = self.amadeus.reference_data.locations.get(
                keyword=place_name,
                subType='CITY'
            )
            if response.data:
                # Return first IATA code found
                return response.data[0].get('iataCode')
        except Exception as e:
            logger.warning(f"Could not resolve IATA for '{place_name}': {e}")
        return None

    def get_coordinates(self, location_name: str):
        """
        Resolves a city/location name to (lat, lon) using Amadeus Locations API.
        Returns: (latitude, longitude) or (None, None)
        """
        if not self.amadeus: return None, None
        
        try:
            logger.info(f"Geocoding location: {location_name}")
            response = self.amadeus.reference_data.locations.get(
                keyword=location_name,
                subType='CITY'
            )
            
            if response.data and len(response.data) > 0:
                # Prioritize first result
                geo = response.data[0]['geoCode']
                return geo['latitude'], geo['longitude']

            # Fallback to OpenStreetMap (Nominatim) if Amadeus fails to resolve name
            return self._geocode_osm(location_name)
                
        except Exception as e:
            logger.error(f"Geocoding Failed: {e}")
            return self._geocode_osm(location_name)

    def _geocode_osm(self, location_name: str):
        import requests
        try:
            headers = {'User-Agent': 'VoiceBot/1.0'}
            url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data:
                    logger.info(f"Geocoded via OSM: {location_name} -> ({data[0]['lat']}, {data[0]['lon']})")
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            logger.error(f"OSM Geocode failed: {e}")
        return None, None

    def search_activities(self, location: str, keyword: str = None) -> List[Dict]:
        """
        Search for tours and activities in a location.
        1. Resolve 'location' (e.g. "Dubai", "Paris") to Coordinates.
        2. Search activities near coordinates.
        """
        lat, lon = self.get_coordinates(location)
        if not lat:
            return []
            
        try:
            logger.info(f"Searching activities near ({lat}, {lon}) keyword={keyword}")
            
            # Amadeus Activities API (Shopping)
            # Typically requires latitude, longitude, and radius
            # Optional: keywords/category filter? Varies by endpoint version.
            # Using basic geo-search first.
            
            # Note: amadeus.shopping.activities.get usually takes (latitude, longitude, radius)
            response = self.amadeus.shopping.activities.get(
                latitude=lat,
                longitude=lon,
                radius=10 # 10km radius
            )
            
            if not response.data:
                return []
                
            # Define family-friendly keywords for semantic matching
            FAMILY_KEYWORDS = [
                'family', 'kids', 'children', 'child', 'toddler', 'baby', 
                'water park', 'zoo', 'aquarium', 'theme park', 'amusement park', 
                'museum', 'play', 'park', 'playground', 'fair', 'circus', 
                'toy', 'animation', 'educational', 'creative', 'garden',
                'adventure', 'sightseeing', 'tour', 'beach', 'interactive'
            ]
            
            is_family_search = keyword and keyword.lower() in ['family friendly', 'family-friendly', 'for kids', 'kids']

            results = []
            for activity in response.data:
                name = activity.get('name', 'Unknown Activity')
                desc = activity.get('shortDescription', '').lower() or activity.get('description', '').lower()
                name_lower = name.lower()
                
                # Check keyword filter
                if keyword:
                    # Special handling for "family friendly"
                    if is_family_search:
                        # Match if any family keyword is in name or description
                        if not any(k in name_lower or k in desc for k in FAMILY_KEYWORDS):
                            continue
                    else:
                        # Standard strict keyword matching for other terms
                        if keyword.lower() not in name_lower and keyword.lower() not in desc:
                            continue
                    
                price_obj = activity.get('price', {})
                currency = price_obj.get('currencyCode', 'EUR')
                amount = price_obj.get('amount', 'N/A')
                booking_link = activity.get('bookingLink', '')
                rating = activity.get('rating', 'N/A')
                
                # Extract image URL from pictures array
                pictures = activity.get('pictures', [])
                image_url = pictures[0] if pictures else None
                
                # Get description
                description = activity.get('shortDescription', '') or activity.get('description', '')
                
                results.append({
                    "name": name,
                    "price": f"{currency} {amount}",
                    "rating": rating,
                    "link": booking_link,
                    "image_url": image_url,
                    "description": description,
                    "details": f"{name} ({currency} {amount}) - Rating: {rating}"
                })
                
            return results[:10] # Top 10

        except Exception as e:
            logger.error(f"Activity Search Failed: {e}")
            return []

    def search_activities_formatted(self, location: str, keyword: str = None) -> str:
        """
        Agent-friendly activity search result.
        """
        activities = self.search_activities(location, keyword)
        
        if not activities:
            return f"No activities found in {location} (via Amadeus)."
            
        summary = f"🎟️ **Activities in {location}**"
        if keyword: summary += f" (filtering for '{keyword}')"
        summary += "\n"
        
        for act in activities:
            summary += f"- **{act['name']}** | {act['price']} | ⭐ {act['rating']}\n"
            # summary += f"  Link: {act['link']}\n" 
            
        return summary

    def search_hotels_formatted(self, city_code_or_name: str = None, latitude: float = None, longitude: float = None, radius: int = 10) -> str:
        """
        Agent-friendly string output with bookability, rankings, and distance.
        """
        if latitude is not None and longitude is not None:
             offers = self.search_hotels_by_location(latitude, longitude, radius)
             loc_desc = f"near ({latitude}, {longitude})"
        elif city_code_or_name:
             # Try to resolve to IATA first
             city_code = city_code_or_name
             if len(city_code) != 3 or not city_code.isupper():
                  resolved = self.resolve_city_to_iata(city_code_or_name)
                  if resolved: city_code = resolved
             offers = self.search_hotels_by_city(city_code)
             loc_desc = city_code
        else:
             return "Error: City code or coordinates required for hotel search."
        
        if not offers:
            return f"No bookable hotel offers found in {loc_desc} via Amadeus."
            
        hotel_ids = [o['hotel_id'] for o in offers]
        sentiments = self.get_hotel_sentiments(hotel_ids)
            
        summary = f"🏨 **Amadeus Bookable Hotel Results ({loc_desc})**\n"
        # Sort by proximity if distance is available (and floatable)
        try:
             def dist_key(o):
                  d_str = o.get('distance', '999')
                  try: return float(d_str.split()[0])
                  except: return 999.0
             offers.sort(key=dist_key)
        except: pass

        for offer in offers:
            h_id = offer['hotel_id']
            summary += f"- **{offer['name']}** | {offer['price']}\n"
            
            # Distance
            dist = offer.get('distance')
            if dist and dist != 'N/A':
                 summary += f"  📍 Distance: {dist} from anchor spot\n"

            # Location info
            addr = offer.get('address', {})
            if addr:
                city = addr.get('cityName', '')
                summary += f"  Loc: {city}\n"
            
            if h_id in sentiments:
                s = sentiments[h_id]
                overall = s.get('overall', 'N/A')
                scores = s.get('scores', {})
                summary += f"  ⭐ Sentiment: {overall}/100\n"
                if scores:
                    itemized = []
                    for k, v in scores.items():
                        # Map internal categories to user-friendly labels
                        label = k.replace('Quality', '').capitalize()
                        itemized.append(f"{label}: {v}")
                    summary += f"  *Ratings: {', '.join(itemized[:4])}*\n"
            
            summary += f"  *Hotel ID: `{h_id}`*\n"
            
        return summary
