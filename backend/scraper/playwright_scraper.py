import asyncio
import os
import json
import urllib.parse
from urllib.parse import urljoin
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from supabase import create_client
import sys

# Ensure backend path is available
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import extract_and_evaluate_opportunities
from notifier import send_whatsapp_alert

load_dotenv()

def get_db():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

async def scrape_and_evaluate_url(page, url: str, source_name: str, source_tier: str, profile: dict, schedule: list):
    print(f"\nNavigating to {source_name} ({url})...", flush=True)
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=15000)
    except Exception as e:
        print(f"Failed to load {url}: {e}")
        return
        
    print(f"Loaded {source_name}. Extracting full page text and links...", flush=True)
    
    extracted = await page.evaluate('''
        () => {
            const tagsToRemove = ['nav', 'footer', 'aside', 'script', 'style'];
            tagsToRemove.forEach(tag => {
                document.querySelectorAll(tag).forEach(el => el.remove());
            });
            let text = document.body.innerText;
            let linkDict = {};
            let currentUrl = window.location.href;
            Array.from(document.querySelectorAll('a')).forEach(a => {
                let href = a.getAttribute('href');
                let linkText = a.innerText.trim();
                // Filter invalid anchors
                if (href && !href.startsWith('#') && !href.toLowerCase().startsWith('javascript:') && linkText.length > 2) {
                    try {
                        let absoluteUrl = new URL(href, currentUrl).href;
                        linkDict[linkText] = absoluteUrl;
                    } catch(e) {}
                }
            });
            return { text: text, links: linkDict, actualUrl: currentUrl };
        }
    ''')
        
    page_text = extracted['text']
    link_dict_json = json.dumps(extracted['links'])
    actual_url = extracted['actualUrl']
        
    if not page_text or len(page_text.strip()) < 50:
        print(f"Page text is empty or too short for {source_name}.")
        return
        
    print("Evaluating page text and extracting opportunities using Gemini...")
    try:
        evaluated_jobs = extract_and_evaluate_opportunities(
            raw_text=page_text,
            link_dict=link_dict_json,
            profile=profile,
            schedule=schedule,
            source_url=actual_url,
            source_name=source_name
        )
        print(f"Gemini returned {len(evaluated_jobs)} evaluated opportunities.")
        
        db = get_db()
        for i, eval_job in enumerate(evaluated_jobs):
            print(f"Saving Job {i+1}: {eval_job.title} (Match: {eval_job.match_score})")
            
            # Boost score if TIER_1_TRUSTED
            if source_tier == "TIER_1_TRUSTED":
                eval_job.match_score = min(100, eval_job.match_score + 10)
                
            opportunity_record = {
                'title': eval_job.title,
                'company': eval_job.company,
                'description': eval_job.description,
                'source_url': actual_url,
                'apply_url': eval_job.apply_url,
                'match_score': eval_job.match_score,
                'schedule_conflict': eval_job.schedule_conflict,
                'schedule_conflict_reason': eval_job.schedule_conflict_reason,
                'legitimacy_score': eval_job.legitimacy_score,
                'fraud_risk_score': eval_job.fraud_risk_score,
                'credibility_flags': eval_job.credibility_flags,
                'pros': eval_job.pros,
                'cons': eval_job.cons,
                'raw_text': f"Extracted via {source_name}",
                'source_name': source_name,
                'source_tier': source_tier,
                'category': eval_job.category,
                'tags': eval_job.tags
            }
            
            if eval_job.apply_url and eval_job.apply_url.strip() and not eval_job.apply_url.startswith('javascript:'):
                opportunity_record['apply_url'] = urljoin(actual_url, eval_job.apply_url)
            elif opportunity_record.get('apply_url'):
                # clear invalid javascript links or bare hashes if somehow returned
                opportunity_record['apply_url'] = urljoin(actual_url, opportunity_record['apply_url'])
                
            is_duplicate = False
            
            # Step 1: Check by apply_url (if it exists)
            if opportunity_record['apply_url']:
                existing_url = db.table('opportunities').select('id').eq('apply_url', opportunity_record['apply_url']).execute()
                if existing_url.data:
                    is_duplicate = True
            
            # Step 2: Check by Title + Company (Fallback)
            if not is_duplicate:
                existing_tc = db.table('opportunities').select('id').eq('title', eval_job.title).eq('company', eval_job.company).execute()
                if existing_tc.data:
                    is_duplicate = True
            
            # Step 3: Insert or Skip
            if not is_duplicate:
                db.table('opportunities').insert(opportunity_record).execute()
                print(f"Successfully inserted '{eval_job.title}'.")
                
                if int(float(eval_job.match_score)) >= 85:
                    try:
                        # Ensure the job data is formatted as a dictionary before sending
                        send_whatsapp_alert(eval_job.model_dump() if hasattr(eval_job, 'model_dump') else eval_job)
                    except Exception as e:
                        print(f"[WhatsApp Deep Crawl Error] {e}")
            else:
                print(f"Job '{eval_job.title}' at '{eval_job.company}' already exists. Skipping duplicate.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error evaluating opportunities for {source_name}: {repr(e)}")

async def run_scrapers():
    db = get_db()
    print("Fetching active web sources from API...", flush=True)
    res = db.table('sources').select('*').eq('source_type', 'WEB').execute()
    web_sources = res.data
    
    if not web_sources:
        print("No WEB sources found in the database. Exiting.")
        return

    profile_res = db.table('user_profiles').select('*').eq('user_id', 'default_user').execute()
    schedule_res = db.table('user_schedules').select('*').eq('user_id', 'default_user').execute()
    
    if not profile_res.data:
        print("No default profile found.")
        return
        
    profile = profile_res.data[0]
    schedule = schedule_res.data

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        for source in web_sources:
            await scrape_and_evaluate_url(
                page=page, 
                url=source['url_or_identifier'], 
                source_name=source['name'], 
                source_tier=source['source_tier'],
                profile=profile,
                schedule=schedule
            )
            await asyncio.sleep(2.5) # Throttle loop
                
        await browser.close()
        print("\nScraping completed.")

if __name__ == "__main__":
    asyncio.run(run_scrapers())
