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
from services import extract_and_evaluate_opportunities, synthesize_directive, refine_directive
import sys
import traceback
import subprocess
import pymupdf as fitz # PyMuPDF
from notifier import send_whatsapp_alert
from scraper.ai_search_agent import run_agentic_search
from scraper.telegram_listener import start_telegram_listener
import asyncio
from datetime import datetime, timezone

from auth import get_current_user, create_access_token, verify_password, get_password_hash
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

def start_agentic_search_sync():
    import asyncio
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_agentic_search())

def run_scrapers_isolated():
    scraper_path = os.path.join(os.path.dirname(__file__), "scraper", "playwright_scraper.py")
    subprocess.Popen([sys.executable, scraper_path])

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check for Telegram session and start listener
    session_string = os.getenv("TELEGRAM_SESSION_STRING")
    session_path = os.path.join(os.path.dirname(__file__), "scraper", "career_agent.session")
    
    if session_string or os.path.exists(session_path):
        asyncio.create_task(start_telegram_listener())
    else:
        print("WARNING: Telegram ingestion disabled. Run 'loginScript.py' to authenticate or set TELEGRAM_SESSION_STRING.")
        
    yield

app = FastAPI(title="AI Career Opportunity Filter API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    opportunity_record = {
        'user_id': current_user_id,
        'title': evaluation.title,
        'company': evaluation.company,
        'description': evaluation.description,
        'source_url': input_data.source_url,
        'apply_url': input_data.apply_url,
        'match_score': evaluation.match_score,
        'schedule_conflict': evaluation.schedule_conflict,
        'schedule_conflict_reason': evaluation.schedule_conflict_reason,
        'legitimacy_score': evaluation.legitimacy_score,
        'fraud_risk_score': evaluation.fraud_risk_score,
        'credibility_flags': evaluation.credibility_flags,
        'cons': evaluation.cons,
        'raw_text': input_data.raw_text,
        'source_name': input_data.source_name,
        'source_tier': input_data.source_tier,
        'category': evaluation.category,
        'tags': evaluation.tags
    }
    is_duplicate = False
    
    # Step 1: Check by apply_url (if it exists)
    if input_data.apply_url:
        existing_url = supabase.table('opportunities').select('id').eq('user_id', current_user_id).eq('apply_url', input_data.apply_url).execute()
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
    else:
        # If it's a duplicate, we can still return a success message but don't insert
        print(f"Job '{evaluation.title}' at '{evaluation.company}' already exists. Skipping duplicate.")
        # Fetch the existing record to return
        existing_record = supabase.table('opportunities').select('*').eq('user_id', current_user_id).eq('title', evaluation.title).eq('company', evaluation.company).execute()
        db_record = existing_record.data[0] if existing_record.data else opportunity_record
        
    # Trigger WhatsApp alert for high-match jobs
    try:
        score_val = int(float(evaluation.match_score))
    except (ValueError, TypeError):
        score_val = 0
        
    if score_val >= 85:
        background_tasks.add_task(
            send_whatsapp_alert,
            opportunity_record
        )
    
    return {"message": "Successfully evaluated and saved", "evaluation": evaluation.model_dump(), "db_record": db_record}

@app.get("/opportunities")
def get_opportunities(current_user_id: str = Depends(get_current_user)):
    try:
        supabase = get_db()
            
        # Fetch all, sorted by match_score desc
        result = supabase.table('opportunities').select('*').eq('user_id', current_user_id).order('match_score', desc=True).execute()
        
        # Apply adaptive match filtering based on source_tier
        filtered_opportunities = []
        for opp in result.data:
            tier = opp.get('source_tier', 'TIER_2_GENERIC')
            score = opp.get('match_score', 0)
            
            if tier == 'TIER_1_TRUSTED' and score >= 10:
                filtered_opportunities.append(opp)
            elif tier == 'TIER_2_GENERIC' and score >= 10:
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

@app.api_route("/health", methods=["GET", "HEAD"])
def health_check(background_tasks: BackgroundTasks):
    try:
        supabase = get_db()
        # Microscopic DB ping to reset Supabase's 7-day inactivity timer
        supabase.table('opportunities').select('id').limit(1).execute()
        
        # Stateful Autonomous Scheduling
        try:
            state_res = supabase.table('system_state').select('*').eq('id', 'singleton').execute()
            
            now = datetime.now(timezone.utc)
            needs_sync = True
            needs_crawl = True
            
            if state_res.data:
                state = state_res.data[0]
                last_sync = state.get('last_sync_timestamp')
                last_crawl = state.get('last_deep_crawl_timestamp')
                
                if last_sync:
                    last_sync_time = datetime.fromisoformat(last_sync)
                    if (now - last_sync_time).total_seconds() < 24 * 3600:
                        needs_sync = False
                        
                if last_crawl:
                    last_crawl_time = datetime.fromisoformat(last_crawl)
                    if (now - last_crawl_time).total_seconds() < 7 * 24 * 3600:
                        needs_crawl = False
            
            if needs_sync or needs_crawl:
                # Update the state immediately so concurrent health checks don't double-trigger
                new_state = {'id': 'singleton'}
                if needs_sync:
                    new_state['last_sync_timestamp'] = now.isoformat()
                    background_tasks.add_task(run_scrapers_isolated)
                if needs_crawl:
                    new_state['last_deep_crawl_timestamp'] = now.isoformat()
                    background_tasks.add_task(start_agentic_search_sync)
                    
                supabase.table('system_state').upsert(new_state).execute()
                
        except Exception as e:
            # If system_state table doesn't exist yet, ignore
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

@app.get("/profile")
def get_profile(current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    if res.data:
        profile = res.data[0]
        # Return structured format for UI
        return {
            "form_preferences": profile.get("form_preferences") or {},
            "raw_resume_text": profile.get("raw_resume_text") or "",
            "ai_filter_directive": profile.get("ai_filter_directive") or "",
            "summary": [] # We don't store summary, just directive, but we can return it as empty array
        }
    return {"form_preferences": {}, "raw_resume_text": "", "ai_filter_directive": ""}

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

@app.post("/profile/save")
def save_profile(input_data: SaveProfileInput, current_user_id: str = Depends(get_current_user)):
    supabase = get_db()
    # Check if profile exists
    res = supabase.table('user_profiles').select('*').eq('user_id', current_user_id).execute()
    
    if res.data:
        # Update existing
        db_result = supabase.table('user_profiles').update({
            'form_preferences': input_data.form_preferences,
            'raw_resume_text': input_data.raw_resume_text,
            'ai_filter_directive': input_data.ai_filter_directive,
            'updated_at': datetime.now(timezone.utc).isoformat()
        }).eq('user_id', current_user_id).execute()
    else:
        # Insert new
        db_result = supabase.table('user_profiles').insert({
            'user_id': current_user_id,
            'form_preferences': input_data.form_preferences,
            'raw_resume_text': input_data.raw_resume_text,
            'ai_filter_directive': input_data.ai_filter_directive
        }).execute()
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
