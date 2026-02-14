
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.append(os.getcwd())

from services.image_search_service import ImageSearchService

class TestImageSearchLogic(unittest.TestCase):
    def setUp(self):
        self.service = ImageSearchService()

    @patch('services.image_search_service.ImageSearchService.search_google_images')
    @patch('services.image_search_service.ImageSearchService.search_pixabay')
    @patch('services.image_search_service.ImageSearchService.search_pexels')
    @patch('services.image_search_service.ImageSearchService.search_wikimedia')
    def test_prefer_google_priority(self, mock_wiki, mock_pexels, mock_pixabay, mock_google):
        # Set up mocks to return something
        mock_google.return_value = "http://google.com/img.jpg"
        mock_pixabay.return_value = "http://pixabay.com/img.jpg"
        
        # Test with prefer_google=True
        result = self.service.search_image("test", prefer_google=True)
        
        # Verify Google was called first and its result returned
        self.assertEqual(result, "http://google.com/img.jpg")
        mock_google.assert_called_once()
        # Pixabay should NOT have been called because Google succeeded
        mock_pixabay.assert_not_called()

    @patch('services.image_search_service.ImageSearchService.search_wikimedia')
    @patch('services.image_search_service.ImageSearchService.search_pixabay')
    def test_wikimedia_pdf_filtering(self, mock_pixabay, mock_wiki):
        # Wikimedia returns a PDF link first, then a good link
        mock_wiki.side_effect = [
            "https://upload.wikimedia.org/wikipedia/commons/test.pdf.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/good.jpg"
        ]
        mock_pixabay.return_value = None
        
        # We need to mock the internal loop to see it retry or skip
        # In our implementation, it just calls the function once per source.
        # So we need to mock search_wikimedia to return the PDF, 
        # then verify it's discarded if possible.
        # Actually, the current implementation calls search_func(query) ONCE.
        # If it returns a PDF, it just continues to the NEXT source.
        
        mock_wiki.return_value = "https://upload.wikimedia.org/wikipedia/commons/test.pdf.jpg"
        mock_pixabay.return_value = "https://pixabay.com/good.jpg"
        
        # Default order starts with Wikimedia
        result = self.service.search_image("test", prefer_google=False)
        
        # Should discard Wikimedia and move to Pixabay
        self.assertEqual(result, "https://pixabay.com/good.jpg")
        mock_wiki.assert_called_once()
        mock_pixabay.assert_called_once()

    @patch('services.image_search_service.ImageSearchService.search_google_images')
    @patch('services.image_search_service.ImageSearchService.search_pixabay')
    def test_hotel_priority(self, mock_pixabay, mock_google):
        mock_pixabay.return_value = "https://pixabay.com/hotel.jpg"
        mock_google.return_value = "https://google.com/hotel.jpg"
        
        # For hotels, even if prefer_google is True, we check the order
        # Wait, the implementation says:
        # if prefer_google: sources.append(('google', ...), ('pixabay', ...))
        # if is_hotel: sources.append(('pixabay', ...), ('google', ...))
        # But prefer_google takes precedence in my if/elif/else
        
        result = self.service.get_hotel_image("Sunrise Stay")
        
        # get_hotel_image calls search_image(..., prefer_google=True, is_hotel=True)
        # So it should hit the prefer_google block and pick Google first if available
        self.assertEqual(result, "https://google.com/hotel.jpg")
        mock_google.assert_called_once()

if __name__ == "__main__":
    unittest.main()
