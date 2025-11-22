from duckduckgo_search import DDGS

def perform_google_search(query: str) -> str:
    """
    Perform a web search (via DuckDuckGo) and return the top results.
    
    Args:
        query: The search query.
        
    Returns:
        A string summary of the top 5 search results.
    """
    try:
        results = []
        # Fetch top 5 results using DuckDuckGo
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=5):
                results.append(f"- {result['title']}: {result['body']} ({result['href']})")
            
        if not results:
            return "No search results found."
            
        return "Top Web Search Results:\n" + "\n".join(results)
        
    except Exception as e:
        return f"Error performing Web Search: {str(e)}"
