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
from services import extract_and_evaluate_opportunities
from notifier import send_whatsapp_alert

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

API_ID = os.environ.get("TELEGRAM_API_ID")
API_HASH = os.environ.get("TELEGRAM_API_HASH")

# Target channels (users can replace these with actual handles or links)
TARGET_CHANNELS = [
    'https://t.me/jobsinternshipswale', 
    'https://t.me/goyalarsh',
    'https://t.me/jobs_and_internships_updates',
    'https://t.me/internfreak',
    't.me/dummytestchannel1',
]

def get_db():
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    return create_client(supabase_url, supabase_key)

def process_telegram_message(message_text, link_dict, source_name):
    print(f"Processing new Telegram message from {source_name}...")
    db = get_db()
    
    profile_res = db.table('user_profiles').select('*').eq('user_id', 'default_user').execute()
    schedule_res = db.table('user_schedules').select('*').eq('user_id', 'default_user').execute()
    
    if not profile_res.data:
        print("No default profile found. Skipping evaluation.")
        return
        
    profile = profile_res.data[0]
    schedule = schedule_res.data
    
    try:
        evaluated_jobs = extract_and_evaluate_opportunities(
            raw_text=message_text,
            link_dict=json.dumps(link_dict),
            profile=profile,
            schedule=schedule,
            source_url=f"https://t.me/{source_name}",
            source_name=source_name
        )
        print(f"Gemini returned {len(evaluated_jobs)} evaluated opportunities from Telegram.")
        
        for eval_job in evaluated_jobs:
            if eval_job.tags is None:
                eval_job.tags = []
            if "Telegram ✈️" not in eval_job.tags:
                eval_job.tags.append("Telegram ✈️")
                
            opportunity_record = {
                'title': eval_job.title,
                'company': eval_job.company,
                'description': eval_job.description,
                'source_url': f"https://t.me/{source_name}",
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
                'source_tier': "TIER_1_TRUSTED",  # Treat Telegram groups as direct trusted sources by default
                'category': eval_job.category,
                'tags': eval_job.tags
            }
            
            is_duplicate = False
            
            # Step 1: Check by apply_url (if it exists)
            if eval_job.apply_url:
                existing_url = db.table('opportunities').select('id').eq('apply_url', eval_job.apply_url).execute()
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
                print(f"Successfully inserted Telegram Job '{eval_job.title}'.")
                
                try:
                    score_val = int(float(eval_job.match_score))
                except (ValueError, TypeError):
                    score_val = 0
                    
                if score_val >= 85:
                    send_whatsapp_alert(opportunity_record)
            else:
                print(f"Job '{eval_job.title}' at '{eval_job.company}' already exists. Skipping duplicate.")
                
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error evaluating Telegram message from {source_name}: {repr(e)}")


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
        print("Telegram Listener: User is not authorized. Please run auth_telegram.py.")
        await client.disconnect()
        return

    print(f"Telegram Listener: Successfully connected. Listening to channels: {TARGET_CHANNELS}")
    
    @client.on(events.NewMessage(chats=TARGET_CHANNELS))
    async def handler(event):
        msg = event.message
        text = msg.message
        if not text:
            return
            
        source_name = "Unknown Channel"
        if event.chat:
            source_name = getattr(event.chat, 'title', getattr(event.chat, 'username', 'Unknown Channel'))
            
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
        await asyncio.to_thread(process_telegram_message, text, link_dict, source_name)
        
    # Wait until disconnected
    await client.run_until_disconnected()
