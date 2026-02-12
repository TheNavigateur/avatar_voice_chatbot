import unittest
from unittest.mock import patch, MagicMock
from tools.market_tools import check_amazon_stock
import json

class TestMarketToolSorting(unittest.TestCase):

    @patch('tools.market_tools.requests.post')
    def test_sorting_logic(self, mock_post):
        # Construct a mock response with mixed items
        mock_response_data = {
            "status_code": 20000,
            "tasks": [{
                "result": [{
                    "items": [
                        {
                            "type": "organic",
                            "title": "Low Rated Sun Cream",
                            "rating": {"value": 3.2},
                            "product_url": "https://amazon.co.uk/dp/low",
                            "price": {"current": 10.00, "displayed_price": "£10.00"},
                            "snippet": "Basic delivery."
                        },
                        {
                            "type": "organic",
                            "title": "Best Rated Prime Sun Cream",
                            "rating": {"value": 4.8},
                            "product_url": "https://amazon.co.uk/dp/best",
                            "price": {"current": 12.00, "displayed_price": "£12.00"},
                            "snippet": "Free Prime Delivery available tomorrow."
                        },
                        {
                            "type": "organic",
                            "title": "Mid Rated Sun Cream",
                            "rating": {"value": 4.5},
                            "product_url": "https://amazon.co.uk/dp/mid",
                            "price": {"current": 11.00, "displayed_price": "£11.00"},
                            "snippet": "Good product."
                        }
                    ]
                }]
            }]
        }

        # Configure the mock to return this data
        mock_response = MagicMock()
        mock_response.json.return_value = mock_response_data
        mock_post.return_value = mock_response

        # Run the function
        result = check_amazon_stock("Sun Cream", "")

        print("\nTest Result Output:\n", result)

        # Assertions
        self.assertIn("Best Rated Prime Sun Cream", result)
        self.assertIn("Rating: 4.8⭐", result)
        self.assertIn("Prime Delivery", result)
        self.assertNotIn("Low Rated Sun Cream", result)

if __name__ == '__main__':
    unittest.main()
