import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.append(os.getcwd())

# Import the tool function directly from agent.py
from agent import add_item_to_package_tool

class TestProductImageFix(unittest.TestCase):

    @patch('agent.BookingService')
    @patch('agent.ImageSearchService')
    def test_add_item_fixes_bad_image(self, MockImageService, MockBookingService):
        # Setup mocks
        mock_image_service = MockImageService.return_value
        mock_image_service.get_product_image.return_value = ["http://example.com/real_image.jpg"]
        
        mock_pkg = MagicMock()
        mock_pkg.title = "Test Trip"
        mock_pkg.items = []
        MockBookingService.add_item_to_package.return_value = mock_pkg
        MockBookingService.get_package.return_value = mock_pkg

        # Test Case 1: "unknown" image URL
        add_item_to_package_tool(
            session_id="test_session",
            package_id="test_pkg",
            item_name="Blue Snorkel",
            item_type="product",
            price=25.0,
            image_url="unknown"
        )
        
        # Verify that get_product_image was called
        mock_image_service.get_product_image.assert_called_with("Blue Snorkel", num=5)
        
        # Verify that the item added to package has the new image URL
        added_item = MockBookingService.add_item_to_package.call_args[0][2]
        self.assertEqual(added_item.metadata['image_url'], "http://example.com/real_image.jpg")

    @patch('agent.BookingService')
    @patch('agent.ImageSearchService')
    def test_add_item_fixes_amazon_product_url_as_image(self, MockImageService, MockBookingService):
        # Setup mocks
        mock_image_service = MockImageService.return_value
        mock_image_service.get_product_image.return_value = ["http://example.com/real_image.jpg"]
        
        mock_pkg = MagicMock()
        mock_pkg.title = "Test Trip"
        mock_pkg.items = []
        MockBookingService.add_item_to_package.return_value = mock_pkg
        MockBookingService.get_package.return_value = mock_pkg

        # Test Case 2: Amazon product URL used as image_url
        bad_url = "https://www.amazon.co.uk/Some-Product/dp/B00HNSSV0S"
        add_item_to_package_tool(
            session_id="test_session",
            package_id="test_pkg",
            item_name="Sunscreen",
            item_type="product",
            price=10.0,
            image_url=bad_url
        )
        
        # Verify that the item added to package has the new image URL instead of the bad one
        added_item = MockBookingService.add_item_to_package.call_args[0][2]
        self.assertEqual(added_item.metadata['image_url'], "http://example.com/real_image.jpg")

if __name__ == "__main__":
    unittest.main()
