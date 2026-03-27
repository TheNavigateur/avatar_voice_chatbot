import requests
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class GetYourGuideService:
    """
    Service to interact with the GetYourGuide (GYG) Partner API.
    Used for activity discovery and multi-item cart management.
    """
    
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.environ.get("GETYOURGUIDE_API_TOKEN")
        self.base_url = "https://api.getyourguide.com/1"
        self.sandbox_url = "https://api.sandbox.getyourguide.com/1"
        self.is_sandbox = os.environ.get("GYG_SANDBOX", "true").lower() == "true"
        
    def _get_url(self, endpoint: str) -> str:
        base = self.sandbox_url if self.is_sandbox else self.base_url
        return f"{base}/{endpoint.lstrip('/')}"
    
    def _get_headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-ACCESS-TOKEN": self.api_token or ""
        }

    def search_activities(self, query: str, location: str = "") -> List[Dict[str, Any]]:
        """
        Search for activities on GetYourGuide.
        """
        if not self.api_token:
            logger.warning("GYG API Token not set. Returning empty results.")
            return []
            
        endpoint = "activities"
        params = {
            "q": query,
            "cnt": 5 # Limit for agent efficiency
        }
        if location:
            params["location"] = location
            
        try:
            response = requests.get(
                self._get_url(endpoint),
                headers=self._get_headers(),
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get("activities", [])
        except Exception as e:
            logger.error(f"Error searching GYG activities: {str(e)}")
            return []

    def create_cart(self, items: List[Dict[str, Any]]) -> Optional[str]:
        """
        Create a shopping cart on GetYourGuide with multiple activities.
        'items' should follow GYG's cart item schema.
        Returns the cart_hash.
        """
        if not self.api_token: return None
        
        endpoint = "carts"
        payload = {"items": items}
        
        try:
            response = requests.post(
                self._get_url(endpoint),
                headers=self._get_headers(),
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            return response.json().get("shopping_cart_hash")
        except Exception as e:
            logger.error(f"Error creating GYG cart: {str(e)}")
            return None

    def get_cart_details(self, cart_hash: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve details and total price for an existing GYG cart.
        """
        if not self.api_token: return None
        
        endpoint = f"carts/{cart_hash}"
        
        try:
            response = requests.get(
                self._get_url(endpoint),
                headers=self._get_headers(),
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error retrieving GYG cart {cart_hash}: {str(e)}")
            return None

    def search_activities_formatted(self, location: str, query: str = "") -> str:
        """
        Returns a formatted string of activities for the agent to present.
        """
        activities = self.search_activities(query, location)
        if not activities:
            return f"No activities found in {location} for '{query}' via GetYourGuide."
            
        res = f"Top activities in {location} via GetYourGuide:\n"
        for i, act in enumerate(activities[:5]):
            title = act.get('title', 'Unknown Activity')
            price_data = act.get('price', {})
            price = price_data.get('starting_price', 0.0)
            currency = price_data.get('currency', 'USD')
            act_id = act.get('activity_id')
            rating = act.get('overall_rating', 'No rating')
            
            res += f"{i+1}. {title} - {currency} {price} (Rating: {rating}) [ITEM_ID: {act_id}]\n"
            
        res += "\n(Note to Agent: Use the [ITEM_ID] in 'propose_itinerary_batch' to enable bundling.)"
        return res
