from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import os
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from supabase import create_client, Client
from models import OpportunityInput, OpportunityEvaluation, SourceInput, FormPreferences
from services import extract_and_evaluate_opportunities, synthesize_directive, refine_directive
import sys
import subprocess
import pymupdf as fitz # PyMuPDF
from notifier import send_whatsapp_alert
from scraper.ai_search_agent import run_agentic_search
from scraper.telegram_listener import start_telegram_listener
import asyncio

def start_agentic_search_sync(user_id="default_user"):
    import asyncio
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(run_agentic_search(user_id))

def run_scrapers_isolated():
    scraper_path = os.path.join(os.path.dirname(__file__), "scraper", "playwright_scraper.py")
    subprocess.Popen([sys.executable, scraper_path])

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scrapers_isolated, 'cron', hour=9, minute=0)
    scheduler.add_job(start_agentic_search_sync, 'cron', day_of_week='mon', hour=10, minute=0, args=['default_user'])
    scheduler.start()
    
    # Check for Telegram session and start listener
    session_path = os.path.join(os.path.dirname(__file__), "scraper", "career_agent.session")
    if os.path.exists(session_path):
        asyncio.create_task(start_telegram_listener())
    else:
        print("WARNING: Telegram ingestion disabled. Run 'auth_telegram.py' to authenticate.")
        
    yield
    scheduler.shutdown()

app = FastAPI(title="AI Career Opportunity Filter API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db() -> Client:
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="Database credentials missing")
    return create_client(supabase_url, supabase_key)

@app.post("/evaluate")
def evaluate_and_save(input_data: OpportunityInput, background_tasks: BackgroundTasks):
    supabase = get_db()

    # Hardcoded default user for Phase 1
    user_id = 'default_user'
    
    # 1. Fetch User Profile
    profile_response = supabase.table('user_profiles').select('*').eq('user_id', user_id).execute()
    if not profile_response.data:
        # Create a mock profile if not exists for testing
        mock_profile = {
            'user_id': user_id,
            'goals': 'Looking for a high-paying software engineering role in product companies. Preferred Location: Pune, Maharashtra, India.',
            'preferred_stipend_min': 50000,
            'learning_focus': 'Full stack development, AI integration'
        }
        supabase.table('user_profiles').insert(mock_profile).execute()
        profile_data = mock_profile
    else:
        profile_data = profile_response.data[0]
        
    # 2. Fetch User Schedule
    schedule_response = supabase.table('user_schedules').select('*').eq('user_id', user_id).execute()
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
        existing_url = supabase.table('opportunities').select('id').eq('apply_url', input_data.apply_url).execute()
        if existing_url.data:
            is_duplicate = True
            
    # Step 2: Check by Title + Company (Fallback)
    if not is_duplicate:
        existing_tc = supabase.table('opportunities').select('id').eq('title', evaluation.title).eq('company', evaluation.company).execute()
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
        existing_record = supabase.table('opportunities').select('*').eq('title', evaluation.title).eq('company', evaluation.company).execute()
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
def get_opportunities():
    supabase = get_db()
        
    # Fetch all, sorted by match_score desc
    result = supabase.table('opportunities').select('*').order('match_score', desc=True).execute()
    
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

@app.post("/sources")
def create_source(source: SourceInput):
    supabase = get_db()
    
    source_record = {
        'name': source.name,
        'url_or_identifier': source.url_or_identifier,
        'source_type': source.source_type,
        'source_tier': source.source_tier
    }
    
    db_result = supabase.table('sources').insert(source_record).execute()
    return {"message": "Source created successfully", "source": db_result.data[0]}

@app.get("/sources")
def get_sources():
    supabase = get_db()
        
    result = supabase.table('sources').select('*').execute()
    return {"sources": result.data}

@app.delete("/sources/{source_id}")
def delete_source(source_id: str):
    supabase = get_db()
        
    supabase.table('sources').delete().eq('id', source_id).execute()
    return {"message": "Source deleted successfully"}

@app.post("/sync-sources")
def sync_sources(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scrapers_isolated)
    return {"message": "Sync started in background"}

@app.post("/search/run-agentic-search")
def run_agentic_search_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(start_agentic_search_sync, 'default_user')
    return {"message": "Agentic search started in background"}

@app.get("/profile")
def get_profile():
    supabase = get_db()
    res = supabase.table('user_profiles').select('*').eq('user_id', 'default_user').execute()
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
def synthesize_profile(input_data: SynthesizeInput):
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
def refine_profile(input_data: RefineInput):
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
def save_profile(input_data: SaveProfileInput):
    supabase = get_db()
    # Upsert profile for default user
    record = {
        'user_id': 'default_user',
        'form_preferences': input_data.form_preferences,
        'raw_resume_text': input_data.raw_resume_text,
        'ai_filter_directive': input_data.ai_filter_directive
    }
    res = supabase.table('user_profiles').upsert(record, on_conflict='user_id').execute()
    return {"message": "Profile saved successfully", "profile": res.data[0]}

# Legacy endpoints (can be kept or removed, but keeping them to not break old UI if needed)
@app.post("/profile")
def update_profile(profile: dict):
    supabase = get_db()
    profile['user_id'] = 'default_user'
    res = supabase.table('user_profiles').upsert(profile, on_conflict='user_id').execute()
    return {"message": "Profile updated", "profile": res.data[0]}

@app.post("/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
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
        supabase.table('user_profiles').upsert({
            'user_id': 'default_user',
            'resume_text': text.strip()
        }, on_conflict='user_id').execute()
        
        return {"message": "Resume parsed successfully", "extracted_text": text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
