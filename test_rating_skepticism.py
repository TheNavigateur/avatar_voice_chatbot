import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add current directory to path
sys.path.append(os.getcwd())

from tools.market_tools import check_amazon_stock

class TestRatingSkepticism(unittest.TestCase):
    
    @patch('tools.market_tools._fetch_amazon_candidates')
    @patch('tools.market_tools._fetch_amazon_reviews')
    def test_quality_markers(self, mock_reviews, mock_candidates):
        mock_reviews.return_value = []
        
        # Test Case 1: High Rating, High Volume (High Quality Match)
        mock_candidates.return_value = [{
            "title": "High Quality Item",
            "url": "https://amazon.co.uk/dp/B0D1234567",
            "rating": {"value": 4.5},
            "rating_count": 100,
            "price": {"displayed_price": "£10.00"},
            "type": "organic"
        }]
        result = check_amazon_stock("item", "details", region="UK")
        self.assertIn("✅ **High Quality Match**", result)
        self.assertIn("Rating: 4.5⭐ (100 ratings)", result)

        # Test Case 2: High Rating, Low Volume (Lower Quality Match)
        mock_candidates.return_value = [{
            "title": "Low Volume Item",
            "url": "https://amazon.co.uk/dp/B0D2234567",
            "rating": {"value": 5.0},
            "rating_count": 2,
            "price": {"displayed_price": "£10.00"},
            "type": "organic"
        }]
        result = check_amazon_stock("item", "details", region="UK")
        self.assertIn("⚠️ **Lower Quality Match**", result)
        self.assertIn("Rating: 5.0⭐ (2 ratings)", result)

        # Test Case 3: High Rating, No Volume (Quality Unverified)
        mock_candidates.return_value = [{
            "title": "No Volume Item",
            "url": "https://amazon.co.uk/dp/B0D3234567",
            "rating": {"value": 5.0},
            "rating_count": 0,
            "price": {"displayed_price": "£10.00"},
            "type": "organic"
        }]
        result = check_amazon_stock("item", "details", region="UK")
        self.assertIn("⚠️ **Quality Unverified**", result)
        
        # Test Case 4: No Rating (Quality Unverified)
        mock_candidates.return_value = [{
            "title": "No Rating Item",
            "url": "https://amazon.co.uk/dp/B0D4234567",
            "rating": None,
            "price": {"displayed_price": "£10.00"},
            "type": "organic"
        }]
        result = check_amazon_stock("item", "details", region="UK")
        self.assertIn("⚠️ **Quality Unverified**", result)

        # Test Case 5: Low Rating, High Volume (Lower Quality Match)
        mock_candidates.return_value = [{
            "title": "Bad Rating Item",
            "url": "https://amazon.co.uk/dp/B0D5234567",
            "rating": {"value": 2.9},
            "rating_count": 100,
            "price": {"displayed_price": "£10.00"},
            "type": "organic"
        }]
        result = check_amazon_stock("item", "details", region="UK")
        self.assertIn("⚠️ **Lower Quality Match**", result)
        self.assertIn("Rating: 2.9⭐ (100 ratings)", result)

if __name__ == "__main__":
    unittest.main()
