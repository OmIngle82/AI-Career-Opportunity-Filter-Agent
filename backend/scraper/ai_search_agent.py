import os
import asyncio
import httpx
from typing import List
from pydantic import BaseModel, Field
from duckduckgo_search import DDGS
from langchain_google_genai import ChatGoogleGenerativeAI
from supabase import create_client
from tenacity import retry, stop_after_attempt, wait_exponential
from playwright.async_api import async_playwright
import sys

# Ensure scraper is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from playwright_scraper import scrape_and_evaluate_url

class SearchQueries(BaseModel):
    queries: List[str] = Field(description="List of 3 to 5 targeted search queries")

def get_db():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=10, max=60))
def generate_search_queries(ai_directive: str, form_preferences: dict) -> List[str]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY missing.")
        return []
    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key)
    structured_llm = llm.with_structured_output(SearchQueries)
    
    prompt = f"""
    Based on the following user profile and AI filtering directive, generate 3 to 5 highly concise, high-impact search queries.
    CRITICAL RULE: Keep queries extremely short (2 to 5 words maximum). Long queries will fail on DuckDuckGo.
    Use combinations like: 'SDE intern Pune', 'GATE 2027 notification', 'PSU engineering recruitment', 'Next.js off campus drive'.
    
    Preferences:
    {form_preferences}
    
    Directive:
    {ai_directive}
    """
    result = structured_llm.invoke(prompt)
    return result.queries

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def search_duckduckgo(query: str):
    with DDGS() as ddgs:
        results = [r for r in ddgs.text(query, max_results=5)]
        return results

async def run_agentic_search(user_id="default_user"):
    print(f"Starting Agentic Search for user: {user_id}")
    db = get_db()
    res = db.table('user_profiles').select('*').eq('user_id', user_id).execute()
    
    if not res.data:
        print("User profile not found.")
        return
        
    profile = res.data[0]
    directive = profile.get("ai_filter_directive")
    preferences = profile.get("form_preferences", {})
    
    if not directive:
        print("No AI directive found. Run compilation first.")
        return
        
    try:
        queries = generate_search_queries(directive, preferences)
    except Exception as e:
        print(f"Error generating queries (Quota/Retry exhausted): {e}")
        queries = ["Software Engineer Pune", "Tech internships .gov.in"]
        
    print(f"Generated queries: {queries}")
    
    if not queries:
        return
        
    schedule_res = db.table('user_schedules').select('*').eq('user_id', user_id).execute()
    schedule = schedule_res.data

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for query in queries:
            print(f"\nExecuting search: {query}")
            try:
                results = await asyncio.to_thread(search_duckduckgo, query)
            except Exception as e:
                print(f"Search failed for '{query}': {e}")
                await asyncio.sleep(5)
                continue
                
            if not results:
                print("No results found for this query.")
                continue
                
            for result in results:
                title = result.get("title", "")
                url = result.get("href", "")
                
                if not url:
                    continue
                    
                print(f"\nDeep Crawling search result: {title}")
                try:
                    await scrape_and_evaluate_url(
                        page=page,
                        url=url,
                        source_name=f"Agentic Search: {query}",
                        source_tier="TIER_2_GENERIC",
                        profile=profile,
                        schedule=schedule
                    )
                except Exception as e:
                    print(f"Deep crawl failed for {url}: {e}")
                    
                await asyncio.sleep(2.5) # Throttle loop
            
            await asyncio.sleep(2.5) # Delay between DDG queries to prevent rate limits
            
        await browser.close()
        print("\nAgentic search completed.")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(run_agentic_search())
