import asyncio
from duckduckgo_search import DDGS
from ..core.config import settings

try:
    from tavily import TavilyClient
    tavily_available = True
except ImportError:
    tavily_available = False

# Initialize Tavily Client
tavily_client = None
if tavily_available and settings.TAVILY_API_KEY:
    tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

def search_web(query: str) -> dict:
    """Searches Tavily (High Quality) or DuckDuckGo (Fallback) and returns results."""
    # Try Tavily first if available
    if tavily_client:
        try:
            print(f"Searching Tavily for: {query[:50]}...")
            # Tavily is optimized for LLM context
            response = tavily_client.search(query, search_depth="advanced", max_results=3)
            if response and response.get('results'):
                results = response['results']
                print(f"Tavily found {len(results)} results.")
                combined_body = "\n".join([f"- {r.get('content', '')}" for r in results])
                return {
                    "title": results[0].get('title', 'Multiple Sources'),
                    "body": combined_body,
                    "href": results[0].get('url', '#')
                }
        except Exception as e:
            print(f"Tavily Search Error: {e}")

    # Fallback to DuckDuckGo
    print(f"Searching DuckDuckGo for: {query[:50]}...")
    try:
        with DDGS() as ddgs:
            # Get more results for better context
            results = list(ddgs.text(query, max_results=5))
            if results:
                print(f"Found {len(results)} results for: {query[:30]}")
                # Combine top 3 results for better evidence
                combined_body = "\n".join([f"- {r.get('body', '')}" for r in results[:3]])
                return {
                    "title": results[0].get('title', 'Multiple Sources'),
                    "body": combined_body,
                    "href": results[0].get('href', '#')
                }
    except Exception as e:
        print(f"Search Error for query '{query}': {e}")
    print(f"No results found for: {query[:30]}")
    return {}

async def search_web_async(query: str) -> dict:
    """Searches DuckDuckGo and returns the first result (Async)."""
    return await asyncio.to_thread(search_web, query)
