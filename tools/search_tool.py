from googlesearch import search

def perform_google_search(query: str) -> str:
    """
    Perform a Google Search and return the top results.
    
    Args:
        query: The search query.
        
    Returns:
        A string summary of the top 5 search results.
    """
    try:
        results = []
        # Fetch top 5 results
        for result in search(query, num_results=5, advanced=True):
            results.append(f"- {result.title}: {result.description} ({result.url})")
            
        if not results:
            return "No search results found."
            
        return "Top Google Search Results:\n" + "\n".join(results)
        
    except Exception as e:
        return f"Error performing Google Search: {str(e)}"
