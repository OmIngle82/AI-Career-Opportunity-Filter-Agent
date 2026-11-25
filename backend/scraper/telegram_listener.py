import os
import sys
import json
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import MessageEntityTextUrl, MessageEntityUrl
from supabase import create_client

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from services import extract_and_evaluate_opportunities
from notifier import notify_new_opportunity_sync
from link_resolver import resolve_opportunity_url

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")

# Default seed channels kept for migration scripts and backward compatibility
TARGET_CHANNELS = [
    'https://t.me/jobsinternshipswale',
    'https://t.me/goyalarsh',
    'https://t.me/jobs_and_internships_updates',
    'https://t.me/internfreak',
    't.me/offcampusjobs4u',
]

import re
import urllib.request
from urllib.parse import urlparse

CAREER_KEYWORDS = [
    r'\bhiring\b', r'\bintern(ship)?\b', r'\bjob(s)?\b', r'\bopening(s)?\b',
    r'\bvacancy\b', r'\bvacancies\b', r'\brole(s)?\b', r'\bapply\b',
    r'\bcareer(s)?\b', r'\bstipend\b', r'\bsalary\b', r'\bctc\b', r'\blpa\b',
    r'\bbatch(es)?\b', r'\beligib(ility|le)\b', r'\bgraduate\b', r'\bfresher(s)?\b',
    r'\bwalk-?in\b', r'\brecruit(ment|ing)?\b', r'\breferral\b', r'\bdeveloper\b',
    r'\bengineer\b', r'\banalyst\b', r'\bexam\b', r'\bnotification\b', r'\bhackathon\b'
]
CAREER_REGEX = re.compile('|'.join(CAREER_KEYWORDS), re.IGNORECASE)

def is_career_relevant(text: str) -> bool:
    if not text or len(text.strip()) < 20:
        return False
    return bool(CAREER_REGEX.search(text))

SHORTENER_DOMAINS = {'bit.ly', 'tinyurl.com', 'cutt.ly', 'rb.gy', 't.co', 'goo.gl', 'shorturl.at', 'rebrand.ly'}

def resolve_canonical_url(url: str, timeout: float = 3.5) -> str:
    if not url or not (url.startswith('http://') or url.startswith('https://')):
        return url
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if any(short in domain for short in SHORTENER_DOMAINS):
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, method='HEAD')
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return response.geturl() or url
    except Exception:
        pass
    return url

def get_db():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

def process_telegram_message(message_text, link_dict, source_name, source_identifier):
    # Pre-LLM Heuristic: filter non-career messages, spam, and channel promotions
    if not is_career_relevant(message_text):
        print(f"[Heuristic Filter] Message from {source_name} has no career signals. Skipping LLM.")
        return

    print(f"Processing new Telegram message from {source_name} ({source_identifier})...")
    db = get_db()
    
    # Find all users tracking this source
    # The source_identifier is typically t.me/username or similar, we'll try a fuzzy match or exact match
    res_sources = db.table('sources').select('user_id').eq('source_type', 'TELEGRAM').ilike('url_or_identifier', f"%{source_identifier}%").execute()
    
    if not res_sources.data:
        print(f"No users tracking this source identifier: {source_identifier}. Skipping.")
        return
        
    # Get distinct user_ids
    user_ids = list(set([s['user_id'] for s in res_sources.data]))
    print(f"Found {len(user_ids)} users tracking {source_identifier}.")
    
    for user_id in user_ids:
        print(f"\n--- Evaluating Telegram message for user: {user_id} ---")
        profile_res = db.table('user_profiles').select('*').eq('user_id', user_id).execute()
        schedule_res = db.table('user_schedules').select('*').eq('user_id', user_id).execute()
        
        if not profile_res.data:
            print(f"No profile found for user {user_id}. Skipping.")
            continue
            
        profile = profile_res.data[0]
        schedule = schedule_res.data
        
        try:
            evaluated_jobs = extract_and_evaluate_opportunities(
                raw_text=message_text,
                link_dict=json.dumps(link_dict),
                profile=profile,
                schedule=schedule,
                source_url=f"https://t.me/{source_identifier}",
                source_name=source_name
            )
            print(f"Gemini returned {len(evaluated_jobs)} evaluated opportunities for user {user_id}.")
            
            for eval_job in evaluated_jobs:
                is_official = bool(eval_job.is_official_source)
                if eval_job.apply_url:
                    resolved_url, detected_official = resolve_opportunity_url(eval_job.apply_url)
                    eval_job.apply_url = resolved_url
                    is_official = is_official or detected_official

                if eval_job.tags is None:
                    eval_job.tags = []
                if "Telegram ✈️" not in eval_job.tags:
                    eval_job.tags.append("Telegram ✈️")
                    
                opportunity_record = {
                    'user_id': user_id,
                    'title': eval_job.title,
                    'company': eval_job.company,
                    'description': eval_job.description,
                    'source_url': f"https://t.me/{source_identifier}",
                    'apply_url': eval_job.apply_url,
                    'match_score': eval_job.match_score,
                    'schedule_conflict': eval_job.schedule_conflict,
                    'schedule_conflict_reason': eval_job.schedule_conflict_reason,
                    'legitimacy_score': eval_job.legitimacy_score,
                    'fraud_risk_score': eval_job.fraud_risk_score,
                    'credibility_flags': eval_job.credibility_flags,
                    'pros': eval_job.pros,
                    'cons': eval_job.cons,
                    'raw_text': f"Extracted via {source_name} (Telegram)",
                    'source_name': f"Telegram: {source_name}",
                    'source_tier': "TIER_1_TRUSTED",
                    'category': eval_job.category,
                    'tags': eval_job.tags,
                    'status': 'INBOX',
                    'eligible_batches': eval_job.eligible_batches,
                    'stipend_or_ctc': eval_job.stipend_or_ctc,
                    'application_deadline': eval_job.application_deadline,
                    'exam_date': eval_job.exam_date,
                    'is_official_source': is_official,
                    'telegram_notified': False,
                }
                
                is_duplicate = False
                
                # Step 1: Check by apply_url (if it exists)
                if eval_job.apply_url:
                    existing_url = db.table('opportunities').select('id').eq('user_id', user_id).eq('apply_url', eval_job.apply_url).execute()
                    if existing_url.data:
                        is_duplicate = True
                
                # Step 2: Check by Title + Company (Fallback)
                if not is_duplicate:
                    existing_tc = db.table('opportunities').select('id').eq('user_id', user_id).eq('title', eval_job.title).eq('company', eval_job.company).execute()
                    if existing_tc.data:
                        is_duplicate = True
                
                # Step 3: Insert or Skip
                if not is_duplicate:
                    ins = db.table('opportunities').insert(opportunity_record).execute()
                    if ins.data:
                        opportunity_record['id'] = ins.data[0]['id']
                    print(f"Successfully inserted Telegram Job '{eval_job.title}' for user {user_id}.")
                    notify_new_opportunity_sync(db, opportunity_record, profile)
                else:
                    print(f"Job '{eval_job.title}' at '{eval_job.company}' already exists for user {user_id}. Skipping duplicate.")
                    
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error evaluating Telegram message from {source_name} for user {user_id}: {repr(e)}")

async def start_telegram_listener():
    if not API_ID or not API_HASH:
        print("Telegram Listener: TELEGRAM_API_ID or TELEGRAM_API_HASH not set.")
        return

    session_string = os.getenv("TELEGRAM_SESSION_STRING")

    if session_string:
        # Cloud production mode
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
    else:
        # Local development fallback
        session_path = os.path.join(os.path.dirname(__file__), 'career_agent.session')
        if not os.path.exists(session_path):
            print(f"Telegram Listener: Session file not found at {session_path}.")
            return
        client = TelegramClient(os.path.join(os.path.dirname(__file__), 'career_agent'), API_ID, API_HASH)
    
    print("Telegram Listener: Starting daemon...")
    await client.connect()
    
    if not await client.is_user_authorized():
        print("Telegram Listener: User is not authorized. Please run scripts/loginScript.py or set TELEGRAM_SESSION_STRING.")
        await client.disconnect()
        return

    # Fetch dynamic channels from database
    db = get_db()
    try:
        response = db.table('sources').select('url_or_identifier').eq('source_type', 'TELEGRAM').execute()
        dynamic_channels = [source['url_or_identifier'] for source in response.data]
    except Exception as e:
        print(f"Telegram Listener: Failed to fetch channels from DB: {e}")
        dynamic_channels = []

    if not dynamic_channels:
        print("Telegram Listener: No Telegram sources found in the database. Exiting.")
        await client.disconnect()
        return

    print(f"Telegram Listener: Successfully connected. Listening to channels: {dynamic_channels}")
    
    @client.on(events.NewMessage(chats=dynamic_channels))
    async def handler(event):
        msg = event.message
        text = msg.message
        if not text:
            return
            
        source_name = "Unknown Channel"
        source_identifier = "Unknown"
        if event.chat:
            chat_title = getattr(event.chat, 'title', None)
            chat_username = getattr(event.chat, 'username', None)
            source_name = chat_title or chat_username or "Unknown Channel"
            source_identifier = chat_username or chat_title or "Unknown"
            
        # Extract links
        link_dict = {}
        if msg.entities:
            for entity in msg.entities:
                if isinstance(entity, MessageEntityTextUrl):
                    link_text = text[entity.offset : entity.offset + entity.length]
                    link_dict[link_text] = entity.url
                elif isinstance(entity, MessageEntityUrl):
                    url = text[entity.offset : entity.offset + entity.length]
                    link_dict[url] = url

        # Process in thread to avoid blocking the event loop
        await asyncio.to_thread(process_telegram_message, text, link_dict, source_name, source_identifier)
        
    # Wait until disconnected
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(start_telegram_listener())

