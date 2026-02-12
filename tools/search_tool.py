from duckduckgo_search import DDGS
from tools.market_tools import _search_organic_live, AMAZON_REGIONS

def perform_google_search(query: str, region: str = "UK") -> str:
    """
    Perform a web search (via DataForSEO or DuckDuckGo) and return top results.
    
    Args:
        query: The search query.
        region: The region code (e.g. "UK", "US", "IN").
        
    Returns:
        A string summary of the top search results.
    """
    # Map region to DataForSEO location_code
    config = AMAZON_REGIONS.get(region, AMAZON_REGIONS["UK"])
    location_code = config.get("location_code", 2826) # Default UK

    # 1. Try DataForSEO first (more reliable)
    try:
        items, error = _search_organic_live(query, location_code=location_code)
        if not error and items:
            results = []
            for item in items[:5]:
                title = item.get("title", "No Title")
                snippet = item.get("description", item.get("snippet", "No description available."))
                url = item.get("url", item.get("link", "#"))
                results.append(f"- {title}: {snippet} ({url})")
            
            if results:
                return f"Top Web Search Results for {config['name']} (via DataForSEO):\n" + "\n".join(results)
    except Exception as e:
        # We print to stdout so it shows up in runner logs if needed
        print(f"DataForSEO search error: {e}")

    # 2. Fallback to DuckDuckGo (doesn't support specific region codes easily, uses default)
    try:
        results = []
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=5):
                results.append(f"- {result['title']}: {result['body']} ({result['href']})")
            
        if not results:
            return "No search results found via DuckDuckGo fallback."
            
        return "Top Web Search Results (via DuckDuckGo):\n" + "\n".join(results)
        
    except Exception as e:
        return f"Error performing Web Search fallback: {str(e)}"
