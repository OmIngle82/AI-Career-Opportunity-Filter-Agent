from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
from urllib.parse import urlparse
import re
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from supabase import create_client, Client
from models import OpportunityInput, OpportunityEvaluation, SourceInput, FormPreferences
from services import (
    extract_and_evaluate_opportunities,
    synthesize_directive,
    refine_directive,
    generate_cold_outreach,
    generate_prep_analysis,
)
import sys
import traceback
import subprocess
import pymupdf as fitz # PyMuPDF
from notifier import (
    send_whatsapp_alert,
    notify_new_opportunity_sync,
    async_send_telegram_bot_alert,
    async_send_telegram_text,
)
from scraper.ai_search_agent import run_agentic_search
from scraper.telegram_listener import start_telegram_listener
from scraper.exam_radar import run_exam_radar
from scraper.link_resolver import resolve_opportunity_url
import asyncio
from datetime import datetime, timezone, timedelta

from auth import get_current_user, create_access_token, verify_password, get_password_hash
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

def start_agentic_search_sync():
    import asyncio
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_agentic_search())

def run_exam_radar_sync():
    asyncio.run(run_exam_radar())

def run_telegram_outbox_retry_sweep():
    """Retries recent (24h) un-notified opportunities capped at 10 items per sweep."""
    try:
        supabase = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        pending = (
            supabase.table('opportunities')
            .select('*')
            .eq('telegram_notified', False)
            .gte('created_at', cutoff)
            .order('created_at', desc=True)
            .limit(10)
            .execute()
        )
        items = pending.data or []
        if not items:
            return
        print(f"[Outbox Sweep] Retrying {len(items)} pending Telegram notifications...")
        profiles_cache = {}
        for opp in items:
            uid = opp.get('user_id')
            if uid not in profiles_cache:
                p_res = supabase.table('user_profiles').select('*').eq('user_id', uid).execute()
                profiles_cache[uid] = p_res.data[0] if p_res.data else {}
            prof = profiles_cache[uid]
            min_score = prof.get('min_alert_score')
            if min_score is None:
                min_score = 60
            if (opp.get('match_score') or 0) < min_score:
                supabase.table('opportunities').update({'telegram_notified': True}).eq('id', opp['id']).execute()
                continue
            chat_id = prof.get('telegram_chat_id') or os.getenv("TELEGRAM_USER_CHAT_ID")
            msg_id = asyncio.run(async_send_telegram_bot_alert(opp, chat_id=chat_id))
            if msg_id:
                supabase.table('opportunities').update({'telegram_notified': True}).eq('id', opp['id']).execute()
    except Exception as e:
        print(f"[Outbox Sweep Warning] {e}")

def run_deadline_reminder_sweep():
    """Sends 48-hour Telegram deadline reminders for SAVED opportunities once."""
    try:
        supabase = get_db()
        now = datetime.now(timezone.utc)
        horizon = (now + timedelta(hours=48)).isoformat()
        res = (
            supabase.table('opportunities')
            .select('*')
            .eq('status', 'SAVED')
            .eq('deadline_reminded', False)
            .gte('application_deadline', now.isoformat())
            .lte('application_deadline', horizon)
            .limit(10)
            .execute()
        )
        items = res.data or []
        if not items:
            return
        profiles_cache = {}
        for opp in items:
            uid = opp.get('user_id')
            if uid not in profiles_cache:
                p_res = supabase.table('user_profiles').select('*').eq('user_id', uid).execute()
                profiles_cache[uid] = p_res.data[0] if p_res.data else {}
            chat_id = profiles_cache[uid].get('telegram_chat_id') or os.getenv("TELEGRAM_USER_CHAT_ID")
            deadline_str = str(opp.get('application_deadline', ''))[:10]
            apply_url = opp.get('apply_url') or opp.get('source_url', '')
            msg = (
                f"⏰ **48-Hour Deadline Reminder!**\n\n"
                f"Your saved opportunity **{opp.get('title')}** at **{opp.get('company')}** closes on **{deadline_str}**.\n"
                f"👉 Apply here: {apply_url}"
            )
            msg_id = asyncio.run(async_send_telegram_text(msg, chat_id=chat_id))
            if msg_id:
                supabase.table('opportunities').update({'deadline_reminded': True}).eq('id', opp['id']).execute()
    except Exception as e:
        print(f"[Deadline Reminder Warning] {e}")

def run_morning_digest_sweep():
    """Sends a daily morning digest of Top 3 matches + Closing Soon deadlines."""
    try:
        supabase = get_db()
        profiles = supabase.table('user_profiles').select('*').eq('daily_digest_enabled', True).execute().data or []
        cutoff_24h = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        for prof in profiles:
            uid = prof.get('user_id')
            chat_id = prof.get('telegram_chat_id') or os.getenv("TELEGRAM_USER_CHAT_ID")
            top_res = (
                supabase.table('opportunities')
                .select('title, company, match_score, category, application_deadline')
                .eq('user_id', uid)
                .gte('created_at', cutoff_24h)
                .gte('match_score', prof.get('min_alert_score') or 60)
                .order('match_score', desc=True)
                .limit(3)
                .execute()
            )
            top_items = top_res.data or []
            if not top_items:
                continue
            lines = ["☀️ **Your Daily Career & Exam Digest:**\n"]
            for i, item in enumerate(top_items, 1):
                dl = f" (Closes {str(item['application_deadline'])[:10]})" if item.get('application_deadline') else ""
                lines.append(f"{i}. **{item['title']}** @ {item['company']} — **{item['match_score']}/100**{dl}")
            lines.append("\nTap `/recent` or `/exams` to triage directly here!")
            asyncio.run(async_send_telegram_text("\n".join(lines), chat_id=chat_id))
    except Exception as e:
        print(f"[Morning Digest Warning] {e}")

def run_scrapers_isolated():
    scraper_path = os.path.join(os.path.dirname(__file__), "scraper", "playwright_scraper.py")
    backend_dir = os.path.dirname(__file__)
    subprocess.Popen([sys.executable, scraper_path], cwd=backend_dir)

scheduler = AsyncIOScheduler()

def check_scheduler_state(trigger_tasks=True, background_tasks: BackgroundTasks = None):
    try:
        supabase = get_db()
        state_res = supabase.table('system_state').select('*').eq('id', 'singleton').execute()
        
        now = datetime.now(timezone.utc)
        needs_sync = True
        needs_crawl = True
        needs_exam_radar = True
        needs_digest = True
        state = state_res.data[0] if (state_res and state_res.data) else {}
        
        last_sync = state.get('last_sync_timestamp')
        last_crawl = state.get('last_deep_crawl_timestamp')
        last_exam = state.get('last_exam_radar_timestamp')
        last_digest = state.get('last_digest_timestamp')
        
        if last_sync:
            last_sync_time = datetime.fromisoformat(last_sync)
            if (now - last_sync_time).total_seconds() < 24 * 3600:
                needs_sync = False
                
        if last_crawl:
            last_crawl_time = datetime.fromisoformat(last_crawl)
            if (now - last_crawl_time).total_seconds() < 7 * 24 * 3600:
                needs_crawl = False

        if last_exam:
            last_exam_time = datetime.fromisoformat(last_exam)
            if (now - last_exam_time).total_seconds() < 12 * 3600:
                needs_exam_radar = False

        if last_digest:
            last_digest_time = datetime.fromisoformat(last_digest)
            if (now - last_digest_time).total_seconds() < 24 * 3600:
                needs_digest = False
        
        if trigger_tasks and (needs_sync or needs_crawl or needs_exam_radar or needs_digest):
            new_state = {
                'id': 'singleton',
                'last_sync_timestamp': now.isoformat() if needs_sync else last_sync,
                'last_deep_crawl_timestamp': now.isoformat() if needs_crawl else last_crawl,
                'last_exam_radar_timestamp': now.isoformat() if needs_exam_radar else last_exam,
                'last_digest_timestamp': now.isoformat() if needs_digest else last_digest,
            }
            supabase.table('system_state').upsert(new_state).execute()
            
            if needs_sync:
                print("[Scheduler] Triggering Daily Web Scrape (Playwright)...")
                if background_tasks:
                    background_tasks.add_task(run_scrapers_isolated)
                else:
                    run_scrapers_isolated()
            if needs_crawl:
                print("[Scheduler] Triggering Weekly Deep Search (Agentic Search)...")
                if background_tasks:
                    background_tasks.add_task(start_agentic_search_sync)
                else:
                    asyncio.create_task(run_agentic_search())
            if needs_exam_radar:
                print("[Scheduler] Triggering 12h Official Exam Radar...")
                if background_tasks:
                    background_tasks.add_task(run_exam_radar_sync)
                else:
                    asyncio.create_task(run_exam_radar())
            if needs_digest:
                if background_tasks:
                    background_tasks.add_task(run_morning_digest_sweep)

        # Always run lightweight outbox retry & 48h deadline reminder checks
        if trigger_tasks and background_tasks:
            background_tasks.add_task(run_telegram_outbox_retry_sweep)
            background_tasks.add_task(run_deadline_reminder_sweep)
                    
        return {"needs_sync": needs_sync, "needs_crawl": needs_crawl, "needs_exam_radar": needs_exam_radar, "state": state}
    except Exception as e:
        print(f"[Scheduler Warning] Failed checking state: {e}")
        return {"error": str(e)}

def cleanup_expired_opportunities(days: int = 30) -> int:
    try:
        supabase = get_db()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        res = supabase.table('opportunities').delete().lt('created_at', cutoff).execute()
        count = len(res.data) if res.data else 0
        if count > 0:
            print(f"[Retention Policy] Successfully purged {count} opportunities older than {days} days (cutoff: {cutoff}).")
        else:
            print(f"[Retention Policy] No opportunities older than {days} days found to purge.")
        return count
    except Exception as e:
        print(f"[Retention Policy Error] Failed to delete expired opportunities: {e}")
        return 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check for Telegram session and start listener
    session_string = os.getenv("TELEGRAM_SESSION_STRING")
    session_path = os.path.join(os.path.dirname(__file__), "scraper", "career_agent.session")
    
    if session_string or os.path.exists(session_path):
        asyncio.create_task(start_telegram_listener())
    else:
        print("WARNING: Telegram ingestion disabled. Run 'loginScript.py' to authenticate or set TELEGRAM_SESSION_STRING.")
        
    # Start Telegram Interactive Bot Service (2-way commands & button callbacks)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if bot_token:
        try:
            from bot_service import start_bot_service
            asyncio.create_task(start_bot_service())
        except Exception as e:
            print(f"[Bot Service Warning] Could not start Telegram Bot Service: {e}")
        
    # Start Autonomous APScheduler (checks every 30 mins, 24h retention purge)
    try:
        scheduler.add_job(check_scheduler_state, 'interval', minutes=30)
        scheduler.add_job(cleanup_expired_opportunities, 'interval', hours=24, args=[30])
        scheduler.start()
        print("[Scheduler] Autonomous APScheduler started (Daily Sync, Weekly Deep Crawl & 30-Day Purge active).")
        # Trigger initial schedule check and cleanup in background
        asyncio.get_event_loop().call_soon(check_scheduler_state)
        asyncio.get_event_loop().call_soon(cleanup_expired_opportunities, 30)
    except Exception as e:
        print(f"[Scheduler Warning] Could not start APScheduler: {e}")

    yield

    try:
        scheduler.shutdown()
    except Exception:
        pass

app = FastAPI(title="AI Career Opportunity Filter API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {
        "status": "online",
        "message": "AI Career Opportunity Filter API is running.",
        "docs_url": "/docs"
    }

def get_db() -> Client:
    raw_url = os.getenv("SUPABASE_URL", "")
    raw_key = os.getenv("SUPABASE_KEY", "")

    # Aggressive sanitization: remove non-printable chars, quotes, and whitespace
    clean_url = re.sub(r'[^\x20-\x7E]', '', raw_url).strip().replace('"', '').replace("'", "")
    clean_key = re.sub(r'[^\x20-\x7E]', '', raw_key).strip().replace('"', '').replace("'", "")

    if not clean_url or not clean_key:
        raise HTTPException(status_code=500, detail="Database credentials missing")

    # Forcefully extract the supabase domain to bypass any malformed protocols or hidden trailing paths
    domain_match = re.search(r'([a-zA-Z0-9-]+\.supabase\.co)', clean_url)
    if domain_match:
        clean_url = f"https://{domain_match.group(1)}"
    else:
        # Fallback for custom domains
        parsed_url = urlparse(clean_url)
        if not parsed_url.scheme:
            clean_url = f"https://{clean_url}"
        elif parsed_url.scheme != 'https':
            clean_url = clean_url.replace(parsed_url.scheme + "://", "https://")

    print(f"Diagnostic - Cleaned URL host: {urlparse(clean_url).hostname}")

    return create_client(clean_url, clean_key)

class UserCreate(BaseModel):
    username: str
    password: str

@app.post("/register")
def register_user(user: UserCreate):
    supabase = get_db()
    
    # Check existing
    res = supabase.table('users').select('id').eq('username', user.username).execute()
    if res.data:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    hashed_pw = get_password_hash(user.password)
    
    try:
        new_user = supabase.table('users').insert({
            'username': user.username,
            'hashed_password': hashed_pw
        }).execute()
        return {"message": "User registered successfully", "user_id": new_user.data[0]['id']}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    supabase = get_db()
    res = supabase.table('users').select('*').eq('username', form_data.username).execute()
    
    if not res.data:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    user = res.data[0]
    if not verify_password(form_data.password, user['hashed_password']):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
        
    access_token = create_access_token(data={"sub": user['id']})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/evaluate")
def evaluate_and_save(input_data: OpportunityInput, background_tasks: BackgroundTasks, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()

    # 1. Fetch User Profile
    profile_response = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    profile_data = profile_response.data[0] if profile_response.data else {}
        
    # 2. Fetch User Schedule
    schedule_response = supabase.table('user_schedules').select('*').eq('user_id', current_user_id).execute()
    schedule_data = schedule_response.data

    # 3. Evaluate via LangChain + Gemini
    try:
        evaluations = extract_and_evaluate_opportunities(
            raw_text=input_data.raw_text, 
            link_dict="{}",
            profile=profile_data, 
            schedule=schedule_data,
            source_url=input_data.source_url or "Unknown",
            source_name=input_data.source_name
        )
        
        if not evaluations:
            raise ValueError("No valid opportunities extracted.")
            
        evaluation = evaluations[0]
        
        # Boost match_score if from a TIER_1_TRUSTED source
        if input_data.source_tier == "TIER_1_TRUSTED":
            evaluation.match_score = min(100, evaluation.match_score + 10)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

    # 4. Save to DB
    resolved_apply_url = input_data.apply_url or evaluation.apply_url
    is_official = bool(evaluation.is_official_source)
    if resolved_apply_url:
        resolved_apply_url, detected_official = resolve_opportunity_url(resolved_apply_url)
        is_official = is_official or detected_official

    opportunity_record = {
        'user_id': current_user_id,
        'title': evaluation.title,
        'company': evaluation.company,
        'description': evaluation.description,
        'source_url': input_data.source_url,
        'apply_url': resolved_apply_url,
        'match_score': evaluation.match_score,
        'schedule_conflict': evaluation.schedule_conflict,
        'schedule_conflict_reason': evaluation.schedule_conflict_reason,
        'legitimacy_score': evaluation.legitimacy_score,
        'fraud_risk_score': evaluation.fraud_risk_score,
        'credibility_flags': evaluation.credibility_flags,
        'cons': evaluation.cons,
        'pros': evaluation.pros,
        'raw_text': input_data.raw_text,
        'source_name': input_data.source_name,
        'source_tier': input_data.source_tier,
        'category': evaluation.category,
        'tags': evaluation.tags,
        'status': 'INBOX',
        'eligible_batches': evaluation.eligible_batches,
        'stipend_or_ctc': evaluation.stipend_or_ctc,
        'application_deadline': evaluation.application_deadline,
        'exam_date': evaluation.exam_date,
        'is_official_source': is_official,
        'telegram_notified': False,
    }
    is_duplicate = False
    
    # Step 1: Check by apply_url (if it exists)
    if resolved_apply_url:
        existing_url = supabase.table('opportunities').select('id').eq('user_id', current_user_id).eq('apply_url', resolved_apply_url).execute()
        if existing_url.data:
            is_duplicate = True
            
    # Step 2: Check by Title + Company (Fallback)
    if not is_duplicate:
        existing_tc = supabase.table('opportunities').select('id').eq('user_id', current_user_id).eq('title', evaluation.title).eq('company', evaluation.company).execute()
        if existing_tc.data:
            is_duplicate = True
            
    # Step 3: Insert or Skip
    if not is_duplicate:
        db_result = supabase.table('opportunities').insert(opportunity_record).execute()
        db_record = db_result.data[0]
        background_tasks.add_task(notify_new_opportunity_sync, supabase, db_record, profile_data)
    else:
        print(f"Job '{evaluation.title}' at '{evaluation.company}' already exists. Skipping duplicate.")
        existing_record = supabase.table('opportunities').select('*').eq('user_id', current_user_id).eq('title', evaluation.title).eq('company', evaluation.company).execute()
        db_record = existing_record.data[0] if existing_record.data else opportunity_record
    
    return {"message": "Successfully evaluated and saved", "evaluation": evaluation.model_dump(), "db_record": db_record}

@app.get("/opportunities")
def get_opportunities(include_low_matches: bool = False, current_user_id: str = Depends(get_current_user)):
    try:
        supabase = get_db()
            
        # Fetch all, sorted by match_score desc
        result = supabase.table('opportunities').select('*').eq('user_id', current_user_id).order('match_score', desc=True).execute()
        
        min_threshold = 10 if include_low_matches else 60
        filtered_opportunities = []
        for opp in result.data:
            score = opp.get('match_score') or 0
            if score >= min_threshold:
                filtered_opportunities.append(opp)
                
        return {"opportunities": filtered_opportunities}
    except Exception as e:
        import sys
        sys.stderr.write(f"\n[API ERROR] {traceback.format_exc()}\n")
        
        raw_url = os.getenv("SUPABASE_URL", "")
        sys.stderr.write(f"Diagnostic - SUPABASE_URL raw length: {len(raw_url)}\n")
        sys.stderr.write(f"Diagnostic - SUPABASE_URL raw repr: {repr(raw_url)}\n")
        
        # Reproduce the cleaning logic to show exactly what is being sent to the client
        clean_url = re.sub(r'[^\x20-\x7E]', '', raw_url).strip().replace('"', '').replace("'", "")
        domain_match = re.search(r'([a-zA-Z0-9-]+\.supabase\.co)', clean_url)
        if domain_match:
            clean_url = f"https://{domain_match.group(1)}"
        else:
            parsed_url = urlparse(clean_url)
            if not parsed_url.scheme:
                clean_url = f"https://{clean_url}"
            elif parsed_url.scheme != 'https':
                clean_url = clean_url.replace(parsed_url.scheme + "://", "https://")
                
            sys.stderr.write(f"Diagnostic - Clean URL given to client: {repr(clean_url)}\n")
        sys.stderr.flush()
        
        raise HTTPException(status_code=500, detail=str(e))

class OpportunityStatusUpdate(BaseModel):
    status: str # 'INBOX', 'SAVED', 'APPLIED', 'DISMISSED'

@app.patch("/opportunities/{opportunity_id}/status")
def update_opportunity_status(
    opportunity_id: str, 
    update_data: OpportunityStatusUpdate, 
    current_user_id: str = Depends(get_current_user)
):
    valid_statuses = {'INBOX', 'SAVED', 'APPLIED', 'DISMISSED'}
    new_status = update_data.status.upper().strip()
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
        
    supabase = get_db()
    res = supabase.table('opportunities').update({'status': new_status}).eq('id', opportunity_id).eq('user_id', current_user_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    return {"message": "Status updated successfully", "opportunity": res.data[0]}

@app.post("/opportunities/{opportunity_id}/generate-outreach")
def generate_outreach_endpoint(
    opportunity_id: str,
    current_user_id: str = Depends(get_current_user)
):
    supabase = get_db()
    opp_res = supabase.table('opportunities').select('*').eq('id', opportunity_id).eq('user_id', current_user_id).execute()
    if not opp_res.data:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opportunity = opp_res.data[0]

    # Return cached draft if already generated
    if opportunity.get('cold_outreach_draft'):
        return {"draft": opportunity['cold_outreach_draft'], "cached": True}

    # Fetch user profile
    prof_res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    profile = prof_res.data[0] if prof_res.data else {}

    try:
        draft = generate_cold_outreach(opportunity, profile)
        supabase.table('opportunities').update({'cold_outreach_draft': draft}).eq('id', opportunity_id).execute()
        return {"draft": draft, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate outreach pitch: {str(e)}")

@app.post("/opportunities/{opportunity_id}/prep")
def generate_prep_endpoint(
    opportunity_id: str,
    current_user_id: str = Depends(get_current_user)
):
    supabase = get_db()
    opp_res = supabase.table('opportunities').select('*').eq('id', opportunity_id).eq('user_id', current_user_id).execute()
    if not opp_res.data:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    opportunity = opp_res.data[0]

    if opportunity.get('prep_analysis'):
        return {"prep": opportunity['prep_analysis'], "cached": True}

    prof_res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    profile = prof_res.data[0] if prof_res.data else {}

    try:
        prep = generate_prep_analysis(opportunity, profile)
        supabase.table('opportunities').update({'prep_analysis': prep}).eq('id', opportunity_id).eq('user_id', current_user_id).execute()
        return {"prep": prep, "cached": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate prep analysis: {str(e)}")

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check(background_tasks: BackgroundTasks):
    try:
        supabase = get_db()
        # Microscopic DB ping to reset Supabase's 7-day inactivity timer
        supabase.table('opportunities').select('id').limit(1).execute()
        
        # Stateful Autonomous Scheduling
        try:
            check_scheduler_state(trigger_tasks=True, background_tasks=background_tasks)
        except Exception as e:
            # If system_state table doesn't exist yet or check fails, non-critical
            pass
            
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        # Return 500 if DB is unreachable so UptimeRobot alerts us
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sources")
def create_source(source: SourceInput, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    
    source_record = {
        'user_id': current_user_id,
        'name': source.name,
        'url_or_identifier': source.url_or_identifier,
        'source_type': source.source_type,
        'source_tier': source.source_tier
    }
    
    db_result = supabase.table('sources').insert(source_record).execute()
    return {"message": "Source created successfully", "source": db_result.data[0]}

@app.get("/sources")
def get_sources(current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
        
    result = supabase.table('sources').select('*').eq('user_id', current_user_id).execute()
    return {"sources": result.data}

@app.delete("/sources/{source_id}")
def delete_source(source_id: str, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
        
    supabase.table('sources').delete().eq('id', source_id).eq('user_id', current_user_id).execute()
    return {"message": "Source deleted successfully"}

@app.post("/sync-sources")
def sync_sources(background_tasks: BackgroundTasks, current_user_id: str = Depends(get_current_user)):
    # Note: Triggering this manually will sync sources for all users in the background.
    background_tasks.add_task(run_scrapers_isolated)
    return {"message": "Sync started in background"}

@app.post("/search/run-agentic-search")
def run_agentic_search_endpoint(background_tasks: BackgroundTasks, current_user_id: str = Depends(get_current_user)):
    background_tasks.add_task(start_agentic_search_sync)
    return {"message": "Agentic search started in background"}

@app.post("/search/run-exam-radar")
def run_exam_radar_endpoint(background_tasks: BackgroundTasks, current_user_id: str = Depends(get_current_user)):
    background_tasks.add_task(run_exam_radar_sync)
    return {"message": "Official Exam Radar started in background"}

@app.post("/cleanup-expired")
def trigger_cleanup_expired(days: int = 30, current_user_id: str = Depends(get_current_user)):
    deleted_count = cleanup_expired_opportunities(days=days)
    return {
        "status": "success",
        "deleted_count": deleted_count,
        "retention_days": days
    }

@app.get("/profile")
def get_profile(current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    if res.data:
        profile = res.data[0]
        return {
            "form_preferences": profile.get("form_preferences") or {},
            "raw_resume_text": profile.get("raw_resume_text") or "",
            "ai_filter_directive": profile.get("ai_filter_directive") or "",
            "graduation_batch": profile.get("graduation_batch") or "",
            "degree_branch": profile.get("degree_branch") or "",
            "experience_level": profile.get("experience_level") or "",
            "target_exam_tracks": profile.get("target_exam_tracks") or [],
            "telegram_chat_id": profile.get("telegram_chat_id") or "",
            "min_alert_score": profile.get("min_alert_score") if profile.get("min_alert_score") is not None else 60,
            "daily_digest_enabled": profile.get("daily_digest_enabled") if profile.get("daily_digest_enabled") is not None else True,
            "summary": []
        }
    return {
        "form_preferences": {},
        "raw_resume_text": "",
        "ai_filter_directive": "",
        "graduation_batch": "",
        "degree_branch": "",
        "experience_level": "",
        "target_exam_tracks": [],
        "telegram_chat_id": "",
        "min_alert_score": 60,
        "daily_digest_enabled": True,
    }

class SynthesizeInput(BaseModel):
    preferences: dict
    resume_text: str = ""

@app.post("/profile/synthesize")
def synthesize_profile(input_data: SynthesizeInput, current_user_id: str = Depends(get_current_user)):
    try:
        synthesis = synthesize_directive(input_data.preferences, input_data.resume_text)
        return synthesis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RefineInput(BaseModel):
    current_summary: List[str]
    current_directive: str
    feedback: str

@app.post("/profile/refine")
def refine_profile(input_data: RefineInput, current_user_id: str = Depends(get_current_user)):
    try:
        synthesis = refine_directive(input_data.current_summary, input_data.current_directive, input_data.feedback)
        return synthesis
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SaveProfileInput(BaseModel):
    form_preferences: dict
    raw_resume_text: str = ""
    ai_filter_directive: str = ""
    graduation_batch: str = ""
    degree_branch: str = ""
    experience_level: str = ""
    target_exam_tracks: List[str] = []
    telegram_chat_id: str = ""
    min_alert_score: int = 60
    daily_digest_enabled: bool = True

@app.post("/profile/save")
def save_profile(input_data: SaveProfileInput, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    
    payload = {
        'form_preferences': input_data.form_preferences,
        'raw_resume_text': input_data.raw_resume_text,
        'ai_filter_directive': input_data.ai_filter_directive,
        'graduation_batch': input_data.graduation_batch,
        'degree_branch': input_data.degree_branch,
        'experience_level': input_data.experience_level,
        'target_exam_tracks': input_data.target_exam_tracks,
        'telegram_chat_id': input_data.telegram_chat_id,
        'min_alert_score': input_data.min_alert_score,
        'daily_digest_enabled': input_data.daily_digest_enabled,
        'updated_at': datetime.now(timezone.utc).isoformat()
    }

    if res.data:
        db_result = supabase.table('user_profiles').update(payload).eq('user_id', current_user_id).execute()
    else:
        payload['user_id'] = current_user_id
        db_result = supabase.table('user_profiles').insert(payload).execute()
    return {"message": "Profile saved successfully", "profile": db_result.data[0]}

# Legacy endpoints (can be kept or removed, but keeping them to not break old UI if needed)
@app.post("/profile")
def update_profile(profile: dict, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    
    if res.data:
        db_result = supabase.table('user_profiles').update(profile).eq('user_id', current_user_id).execute()
    else:
        profile['user_id'] = current_user_id
        db_result = supabase.table('user_profiles').insert(profile).execute()
        
    return {"message": "Profile updated", "profile": db_result.data[0]}

@app.post("/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...), current_user_id: str = Depends(get_current_user)):
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        content = await file.read()
        doc = fitz.open(stream=content, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
            
        # Update user profile with extracted text
        supabase = get_db()
        res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
        
        if res.data:
            supabase.table('user_profiles').update({
                'resume_text': text.strip()
            }).eq('user_id', current_user_id).execute()
        else:
            supabase.table('user_profiles').insert({
                'user_id': current_user_id,
                'resume_text': text.strip()
            }).execute()
        
        return {"message": "Resume parsed successfully", "extracted_text": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
