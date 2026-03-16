import os
import requests
import logging
from typing import List, Dict, Optional
import datetime

logger = logging.getLogger(__name__)

class DuffelService:
    BASE_URL = "https://api.duffel.com"
    VERSION = "v1" # or 'beta' depending on endpoint
    
    def __init__(self):
        self.token = os.environ.get("DUFFEL_ACCESS_TOKEN")
        if not self.token:
            logger.warning("DUFFEL_ACCESS_TOKEN not set. Duffel Service disabled.")
            self.headers = {}
        else:
            self.headers = {
                "Authorization": f"Bearer {self.token}",
                "Duffel-Version": "v2",
                "Content-Type": "application/json",
                "Accept-Encoding": "gzip"
            }

    def _post(self, endpoint: str, data: Dict) -> Dict:
        if not self.token: return {}
        url = f"{self.BASE_URL}{endpoint}"
        try:
            resp = requests.post(url, json={"data": data}, headers=self.headers)
            if resp.status_code not in [200, 201]:
                logger.error(f"Duffel API Error ({resp.status_code}): {resp.text}")
                return {}
            return resp.json().get("data", {})
        except Exception as e:
            logger.error(f"Duffel Request Failed: {e}")
            return {}

    def resolve_place(self, query: str) -> Optional[str]:
        """
        Resolves a place name (city, airport) to an IATA code using Duffel's suggestions API.
        """
        if not self.token: return None
        url = f"{self.BASE_URL}/places/suggestions?query={query}"
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json().get("data", [])
                if data:
                    # Return the first result's IATA code
                    # Usually 'icao_code' or 'iata_code'
                    return data[0].get("iata_code")
        except Exception as e:
            logger.error(f"Duffel Place Resolution Failed: {e}")
        return None

    def search_flights_oneway(self, origin: str, destination: str, date: str) -> List[Dict]:
        """
        Search for one-way flights using raw API.
        """
        logger.info(f"Searching Duffel (Requests) for flights: {origin} -> {destination} on {date}")
        
        payload = {
            "slices": [{
                "origin": origin,
                "destination": destination,
                "departure_date": date
            }],
            "passengers": [{"type": "adult"}],
            "cabin_class": "economy"
        }
        
        # POST /air/offer_requests params usually return offers directly in 'offers' field of response
        # or we might need to query ?return_offers=true if supported, but default is usually to return limited offers
        # Actually Duffel API v1 /air/offer_requests returns the created request which contains 'offers' list.
        
        data = self._post("/air/offer_requests?return_offers=true", payload)
        if not data: return []
        
        offers = data.get("offers", [])
        
        # Sort by total_amount 
        # amounts are strings in Duffel "123.45"
        try:
            sorted_offers = sorted(offers, key=lambda x: float(x.get("total_amount", "999999")))[:5]
        except:
            sorted_offers = offers[:5]

        results = []
        for offer in sorted_offers:
            owner = offer.get("owner", {})
            airline = owner.get("name", "Unknown Airline")
            currency = offer.get("total_currency", "GBP")
            amount = offer.get("total_amount", "0.00")
            
            # Slices -> Segments
            segments_summary = []
            duration_str = ""
            
            slices = offer.get("slices", [])
            if slices:
                first_slice = slices[0]
                duration_str = first_slice.get("duration", "") # PT2H30M
                
                for seg in first_slice.get("segments", []):
                    carrier = seg.get("operating_carrier", {}).get("iata_code", "")
                    number = seg.get("operating_carrier_flight_number", "")
                    dep = seg.get("origin", {}).get("iata_code", "")
                    arr = seg.get("destination", {}).get("iata_code", "")
                    
                    dep_at = seg.get("departing_at", "") # ISO string
                    arr_at = seg.get("arriving_at", "")
                    
                    try:
                        # Simple time extraction 2023-10-25T10:00:00
                        dep_time = dep_at.split("T")[1][:5]
                        arr_time = arr_at.split("T")[1][:5]
                        segments_summary.append(f"{carrier}{number} ({dep} {dep_time}-{arr} {arr_time})")
                    except:
                         segments_summary.append(f"{carrier}{number} ({dep}-{arr})")

            route_str = ", ".join(segments_summary)
            
            results.append({
                "id": offer.get("id"),
                "airline": airline,
                "price": f"{currency} {amount}",
                "amount_float": float(amount),
                "currency": currency,
                "route": route_str,
                "duration": duration_str,
                "details": f"{airline} Flight {route_str}"
            })
            
        return results

    def search_flights_formatted(self, origin: str, destination: str, date: str, end_date: str = None) -> str:
        if not end_date:
            offers = self.search_flights_oneway(origin, destination, date)
            search_desc = f"on {date}"
        else:
            # Search across range (max 7 days to avoid long waits/rate limits)
            try:
                start = datetime.datetime.strptime(date, "%Y-%m-%d")
                end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                days = (end - start).days + 1
                if days > 7:
                    logger.warning(f"Date range too large ({days} days), limiting to 7 days from {date}")
                    days = 7
                
                all_offers = []
                for i in range(days):
                    current_date = (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                    day_offers = self.search_flights_oneway(origin, destination, current_date)
                    for o in day_offers:
                        o['date'] = current_date # Tag with date
                    all_offers.extend(day_offers)
                
                # Sort all by price and take top 5
                all_offers.sort(key=lambda x: x.get('amount_float', 999999))
                offers = all_offers[:5]
                search_desc = f"between {date} and {end_date}"
            except Exception as e:
                logger.error(f"Error searching flight range: {e}")
                offers = self.search_flights_oneway(origin, destination, date)
                search_desc = f"on {date} (range search failed)"

        if not offers:
            return f"No flights found from {origin} to {destination} {search_desc} (via Duffel)."
            
        summary = f"✈️ **Duffel Flight Results ({origin} -> {destination} {search_desc})**\n"
        for offer in offers:
            date_info = f" on {offer['date']}" if 'date' in offer else ""
            summary += f"- **{offer['airline']}**{date_info} | {offer['price']}\n"
            summary += f"  Route: {offer['route']}\n" 
            summary += f"  BOOKING_ID: {offer['id']}\n"
        return summary

    def search_hotels(self, location_keyword: str, check_in: str, check_out: str) -> str:
        """
        Search for hotels using Duffel Stays.
        Requires resolving 'location_keyword' to coordinates.
        For MVP, we will try to stick to a known default or use a geocoder.
        """
        # 1. Geocode (Simple OpenStreetMap for now)
        lat, lon = self._geocode(location_keyword)
        if not lat:
            return f"Could not find location coordinates for '{location_keyword}'."
            
        logger.info(f"Searching Duffel Stays logic for {location_keyword} ({lat}, {lon})")
        
        # 2. Search Stays
        # Endpoint: POST /stays/search
        payload = {
            "location": {
                "radius": {
                    "km": 10,
                    "origin": {"latitude": lat, "longitude": lon}
                }
            },
            "check_in_date": check_in,
            "check_out_date": check_out,
            "rooms": 1,
            "guests": [{"type": "adult"}]
        }
        
        data = self._post("/stays/search", payload)
        # Duffel Stays search returns 'results' or 'accommodations'?
        # Actually it returns a list of 'search_results' or equivalent.
        # Let's inspect 'data'.
        
        # Note: Stays API might return an ID and strictly require a second step to get rates?
        # Or it returns a list of accommodations with lead rates.
        # Let's assume it returns a list of accommodations.
        
        results = data.get("results", []) # simplified guess, need to verify
        if not results:
             # Try 'accommodations' maybe?
             results = data.get("accommodations", [])
             
        if not results:
            return f"No hotel results found in {location_keyword}."
            
        summary = f"🏨 **Duffel Hotel Results ({location_keyword})**\n"
        count = 0
        for item in results:
            # item might be an accommodation object
            name = item.get("accommodation", {}).get("name", "Unknown Hotel")
            # Rate?
            # usually under 'cheapest_rate' or similar in search results
            rate = item.get("cheapest_rate", {})
            currency = rate.get("currency", "GBP")
            amount = rate.get("total_amount", "N/A")
            
            summary += f"- **{name}** | {currency} {amount}\n"
            summary += f"  BOOKING_ID: {item.get('id') or item.get('accommodation', {}).get('id')}\n"
            count += 1
            if count >= 5: break
            
        return summary
        
    def _geocode(self, city: str):
        # Quick and dirty free geocoding
        try:
            # User-Agent required by Nominatim
            headers = {'User-Agent': 'VoiceBot/1.0'}
            url = f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1"
            res = requests.get(url, headers=headers)
            if res.status_code == 200:
                data = res.json()
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
        return None, None
    
    def create_order(self, offer_id: str, passengers: List[Dict], payment_intent_id: Optional[str] = None) -> Optional[Dict]:
        """
        Creates a flight order on Duffel.
        """
        if not self.token: return None
        
        payload = {
            "type": "instant",
            "selected_offers": [offer_id],
            "passengers": passengers,
            "payments": [{"type": "balance", "amount": "0.00", "currency": "GBP"}] # placeholder for sandbox/test
        }
        
        if payment_intent_id:
            payload["payments"] = [{"type": "payment_intent", "id": payment_intent_id}]

        logger.info(f"Creating Duffel Order for offer: {offer_id}")
        data = self._post("/air/orders", payload)
        return data

    def create_payment_intent(self, amount: str, currency: str) -> Optional[Dict]:
        """
        Creates a Payment Intent on Duffel for charging a card.
        """
        if not self.token: return None
        payload = {
            "amount": amount,
            "currency": currency
        }
        logger.info(f"Creating Duffel Payment Intent for {currency} {amount}")
        data = self._post("/payments/payment_intents", payload)
        return data

    def create_stay_order(self, quote_id: str, lead_guest: Dict) -> Optional[Dict]:
        """
        Creates a hotel booking (Stay) on Duffel.
        """
        if not self.token: return None
        
        payload = {
            "quote_id": quote_id,
            "guests": [lead_guest],
            "email": lead_guest.get("email"),
            "phone_number": lead_guest.get("phone_number"),
            "payments": [{"type": "balance", "amount": "0.00", "currency": "GBP"}] # sandbox default
        }
        
        logger.info(f"Creating Duffel Stay Order for quote: {quote_id}")
        data = self._post("/stays/bookings", payload)
        return data

    def get_stay_quote(self, rate_id: str) -> Optional[Dict]:
        """
        Gets a final quote for a hotel rate before booking.
        """
        if not self.token: return None
        logger.info(f"Getting Duffel Stay Quote for rate: {rate_id}")
        data = self._post("/stays/quotes", {"rate_id": rate_id})
        return data
