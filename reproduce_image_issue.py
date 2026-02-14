
import os
import sys

# Add current directory to path
sys.path.append(os.getcwd())

from services.image_search_service import ImageSearchService
import logging

logging.basicConfig(level=logging.INFO)

def test_search():
    service = ImageSearchService()
    
    # The query used in get_hotel_image for "Sunrise Stay"
    query = "Sunrise Stay room"
    print(f"Testing search for: {query}")
    
    wikimedia_result = service.search_wikimedia(query)
    print(f"Wikimedia result: {wikimedia_result}")
    
    # Test with "hotel" instead of "room"
    query_hotel = "Sunrise Stay hotel"
    print(f"Testing search for: {query_hotel}")
    wikimedia_result_hotel = service.search_wikimedia(query_hotel)
    print(f"Wikimedia result (hotel): {wikimedia_result_hotel}")

    # Test the main search_image method
    main_result = service.get_hotel_image("Sunrise Stay")
    print(f"Main get_hotel_image result: {main_result}")

if __name__ == "__main__":
    test_search()
