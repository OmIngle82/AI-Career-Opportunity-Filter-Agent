import os
import re
from datetime import datetime, timezone
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from models import OpportunityEvaluation, ProfileSynthesis, OpportunityEvaluations, PrepAnalysis
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from langchain_google_genai.chat_models import GoogleAPIError
from langchain_groq import ChatGroq
import groq
from groq import Groq

def should_retry_exception(exception):
    return isinstance(exception, (ResourceExhausted, ServiceUnavailable, GoogleAPIError))

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception(should_retry_exception))
def synthesize_directive(preferences: dict, resume: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key)
    
    prompt = PromptTemplate.from_template("""
    You are an AI Persona Compiler. Synthesize the following user preferences and resume into a concise summary and a strict AI Filter Directive.
    
    User Preferences:
    {preferences}
    
    Resume Text:
    {resume}
    
    Output a structured object with two fields, formatted explicitly with Markdown and clean newlines (\\n\\n):
    
    1. 'summary': A JSON array of exactly 3 strings representing the user's career profile paragraphs (e.g., ["**Professional Overview**\\n<text>", "**Target Roles & Locations**\\n<text>", "**Proactive Exam & Public Sector Tracking**\\n<text>"]).
    
    2. 'directive': A strict, robust filtering directive outlining exactly how another AI should score and flag opportunities for this user. You MUST generate exactly 6 explicit numbered rules separated by double newlines (\\n\\n):
       1. **Role Alignment:** (Hard rejection of non-software/DevOps/user-targeted roles)
       2. **Geographic & Work Mode Constraints:** (Location boundaries based on user preferences)
       3. **Tech Stack Requirements:** (Specific language & framework scoring)
       4. **Availability & Schedule Fit:** (Study blocks & education balance)
       5. **Career Stage:** (Strictly 0-2 years / Intern / Entry-level; reject Senior roles unless requested)
       6. **Proactive Exam & Government Tracking:** (Actively detect, score, and flag official notifications, registration windows, and application deadlines for target exams. Strongly boost technical vacancies, IT officer posts, and engineering roles from government, PSU, and public sector portals that align with the user's technical background.)
    """)
    
    structured_llm = llm.with_structured_output(ProfileSynthesis)
    result = structured_llm.invoke(prompt.format_prompt(preferences=str(preferences), resume=resume).to_messages())
    return result.model_dump()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception(should_retry_exception))
def refine_directive(current_summary: list, current_directive: str, feedback: str) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key)
    
    prompt = PromptTemplate.from_template("""
    You are an AI Persona Compiler. Based on the user's new feedback, refine their current profile summary and AI filter directive.
    
    Current Summary: {summary}
    Current Directive: {directive}
    
    User Feedback/Adjustment: {feedback}
    
    Update both the summary and the directive to incorporate the user's feedback. Make sure the directive remains strict.
    CRITICAL: Preserve and adapt any proactive exam and government tracking instructions from the current directive when generating the new one.
    
    FORMATTING RULES (Strictly enforce Markdown and clean newlines \\n\\n):
    - Summary MUST be a JSON array of exactly 3 strings (e.g., ["**Professional Overview**\\n...", "**Target Roles...**\\n...", "**Proactive Exam...**\\n..."]).
    - Directive MUST be exactly 6 numbered rules separated by double newlines (\\n\\n):
      1. **Role Alignment:**
      2. **Geographic & Work Mode Constraints:**
      3. **Tech Stack Requirements:**
      4. **Availability & Schedule Fit:**
      5. **Career Stage:**
      6. **Proactive Exam & Government Tracking:**
    """)
    
    structured_llm = llm.with_structured_output(ProfileSynthesis)
    result = structured_llm.invoke(prompt.format_prompt(summary=current_summary, directive=current_directive, feedback=feedback).to_messages())
    return result.model_dump()

SCAM_FEE_PATTERNS = [
    r'registration\s+fee\s+for\s+(job|internship|interview|offer)',
    r'training\s*-?\s*cum\s*-?\s*internship',
    r'training\s+fee',
    r'security\s+deposit',
    r'refundable\s+deposit',
    r'buy\s+certificate',
    r'guaranteed\s+placement\s+for',
    r'pay\s+(?:rs\.?|inr|₹)\s*\d+',
]
SCAM_FEE_REGEX = re.compile('|'.join(SCAM_FEE_PATTERNS), re.IGNORECASE)

OFFICIAL_EXAM_DOMAINS = (
    '.gov.in', '.nic.in', '.ac.in', '.edu.in', 'tcs.com', 'gate20', 'iit',
    'isro.gov.in', 'drdo.gov.in', 'barc.gov.in', 'nielit.gov.in', 'sih.gov.in'
)

def parse_iso_date_safe(val: Optional[str]) -> Optional[str]:
    """Safely parses LLM-extracted date strings into UTC ISO timestamps, returning None on invalid inputs."""
    if not val or not isinstance(val, str):
        return None
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in ('null', 'none', 'n/a', 'na', 'tbd', 'unknown'):
        return None
    try:
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', cleaned):
            dt = datetime.strptime(cleaned, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            return dt.isoformat()
        dt = datetime.fromisoformat(cleaned.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        pass
    for fmt in ('%d-%m-%Y', '%d/%m/%Y', '%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y'):
        try:
            dt = datetime.strptime(cleaned, fmt).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            continue
    return None

def apply_student_eligibility_and_scam_guards(
    eval_job: OpportunityEvaluation,
    profile: dict,
    raw_text: str = ""
) -> OpportunityEvaluation:
    """Enforces hard graduation batch, experience, and paid-internship scam caps in Python."""
    if eval_job.cons is None:
        eval_job.cons = []
    if eval_job.credibility_flags is None:
        eval_job.credibility_flags = []

    eval_job.application_deadline = parse_iso_date_safe(eval_job.application_deadline)
    eval_job.exam_date = parse_iso_date_safe(eval_job.exam_date)

    exp_level = str(profile.get('experience_level') or '').lower()
    is_student_or_fresher = not exp_level or any(k in exp_level for k in ('student', 'fresher', 'intern', '0-1'))
    if is_student_or_fresher and eval_job.min_experience_years is not None and eval_job.min_experience_years >= 2:
        eval_job.match_score = min(eval_job.match_score, 25)
        msg = f"Requires {eval_job.min_experience_years}+ yrs experience (exceeds student/fresher level)"
        if msg not in eval_job.cons:
            eval_job.cons.append(msg)

    form_prefs = profile.get('form_preferences') or {}
    user_batch = str(profile.get('graduation_batch') or form_prefs.get('graduation_batch') or '').strip()
    if user_batch and eval_job.eligible_batches:
        norm_batches = [str(b).strip().lower() for b in eval_job.eligible_batches if b]
        if norm_batches and not any(k in b for b in norm_batches for k in ('any', 'all', 'open', user_batch.lower())):
            eval_job.match_score = min(eval_job.match_score, 25)
            msg = f"Batch mismatch: targets {', '.join(eval_job.eligible_batches)} (your batch: {user_batch})"
            if msg not in eval_job.cons:
                eval_job.cons.append(msg)

    apply_lower = (eval_job.apply_url or '').lower()
    is_official_exam = (eval_job.category == 'Exam') and any(dom in apply_lower for dom in OFFICIAL_EXAM_DOMAINS)
    combined_text = f"{eval_job.title} {eval_job.description} {raw_text[:2000]}"
    if not is_official_exam and SCAM_FEE_REGEX.search(combined_text):
        eval_job.match_score = min(eval_job.match_score, 15)
        eval_job.fraud_risk_score = max(eval_job.fraud_risk_score, 85)
        eval_job.legitimacy_score = min(eval_job.legitimacy_score, 20)
        scam_msg = "Potential paid-internship / fee scam detected"
        if scam_msg not in eval_job.cons:
            eval_job.cons.append(scam_msg)
        if scam_msg not in eval_job.credibility_flags:
            eval_job.credibility_flags.append(scam_msg)

    return eval_job

# Removed retry decorator to manually manage rate limit rotation
def extract_and_evaluate_opportunities(raw_text: str, link_dict: str, profile: dict, schedule: list, source_url: str, source_name: str) -> list[OpportunityEvaluation]:
    ai_directive = profile.get("ai_filter_directive")
    form_prefs = profile.get("form_preferences") or {}
    student_context = (
        f"Graduation Batch: {profile.get('graduation_batch') or form_prefs.get('graduation_batch') or 'Unspecified'} | "
        f"Degree/Branch: {profile.get('degree_branch') or form_prefs.get('degree_branch') or 'Unspecified'} | "
        f"Experience Level: {profile.get('experience_level') or form_prefs.get('experience_level') or 'Student / Fresher (0-1 yr)'} | "
        f"Target Exam Tracks: {profile.get('target_exam_tracks') or form_prefs.get('target_exam_tracks') or []}"
    )
    schedule_str = "\\n".join([f"- {s.get('event_name')}: {s.get('start_date')} to {s.get('end_date')}" for s in schedule])
    if not schedule_str:
        schedule_str = "No upcoming schedule constraints."

    evaluation_prompt = PromptTemplate.from_template("""
    You are an expert career counselor and cybersecurity AI. Your goal is to simultaneously EXTRACT and EVALUATE the top 3 career opportunities (jobs, internships, exams) from the provided raw text.
    
    STUDENT ELIGIBILITY CONTEXT:
    {student_context}

    STRICT AI FILTER DIRECTIVE (Use this to evaluate the opportunities):
    {directive}
    
    User Schedule Constraints:
    {schedule}
    
    Opportunity Source URL: {source_url}
    Opportunity Source Name: {source_name}

    Raw Page Text:
    {raw_text}
    
    JSON Link Dictionary:
    {link_dict}

    You must ALWAYS respond by calling the provided extraction tool. If no jobs match the strict filter criteria, you must call the tool with an empty array. NEVER output plain conversational text or explanations.

    INSTRUCTIONS:
    1. Extract up to 3 high-quality career opportunities found in the Raw Page Text.
    2. For EACH opportunity, select the exact Absolute Application URL from the 'JSON Link Dictionary'. This is mandatory.
       PRIORITIZE: When extracting the apply_url for an Exam or Government Job, prioritize official domains (.gov.in, .nic.in, .ac.in, .edu.in, tcs.com) over aggregator or news domains whenever multiple links are present.
    3. Evaluate EACH opportunity based on the STRICT AI FILTER DIRECTIVE and STUDENT ELIGIBILITY CONTEXT.
    4. Extract structured student fields whenever mentioned:
       - eligible_batches: list of graduation years (e.g. ["2026", "2027"] or ["Any"])
       - min_experience_years: integer (0 for student/intern/fresher, 2+ if experienced)
       - stipend_or_ctc: e.g. "50k/month" or "12 LPA"
       - application_deadline: YYYY-MM-DD if stated, else null
       - exam_date: YYYY-MM-DD if stated, else null
       - is_official_source: true if apply_url is an official career/ATS/.gov.in/.ac.in portal
    5. Provide a match_score (0-100), legitimacy_score (0-100), fraud_risk_score (0-100), credibility_flags, pros, and cons.
    6. Strictly classify the opportunity into one of the allowed categories: 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'.
       EXAM DEFINITION: 'Exam' must ONLY be used for official corporate national drives (e.g. TCS NQT, CodeVita), official government/PSU recruitment notifications (GATE, ISRO, DRDO, BARC, NIC), official university exam registrations, or official hackathons.
       COMMERCIAL COURSE FILTER: If the text is promoting a commercial coaching course, mock test series, bootcamp, or tutorial, set category to 'Other' and score below 30.
       PAID-INTERNSHIP / JOB FEE SCAM FILTER: If a job or internship asks candidates to pay a registration fee, training fee, or deposit, penalize match_score below 20 and raise fraud_risk_score above 80. (EXEMPT legitimate exam fees on official .gov.in/.ac.in portals like GATE/ISRO/DRDO, which are valid 'Exam' listings).
    7. Extract 3-4 short, highly relevant tags (e.g., tech stack like 'Next.js', work mode like 'Remote', or exam name like 'GATE').
    """)
    
    prompt_value = evaluation_prompt.format_prompt(
        student_context=student_context,
        directive=ai_directive or "No strict directive available.",
        schedule=schedule_str,
        raw_text=raw_text[:25000],
        link_dict=link_dict[:15000],
        source_url=source_url,
        source_name=source_name
    )
    
    # 1. Initialize Primary LLM and bind structured output
    primary_llm = ChatGoogleGenerativeAI(
        model="gemini-3.6-flash",
        google_api_key=os.environ.get("GEMINI_API_KEY"),
        temperature=0.1,
    )
    primary_structured = primary_llm.with_structured_output(OpportunityEvaluations)

    # 2. Initialize Fallback LLMs and bind structured output
    fallbacks_structured = []
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            print("[Groq] Using hardcoded model: openai/gpt-oss-120b")
            groq_llm = ChatGroq(
                model="openai/gpt-oss-120b",
                api_key=groq_key,
                temperature=0.1,
            )
            fallbacks_structured.append(groq_llm.with_structured_output(OpportunityEvaluations))
        except Exception as e:
            print(f"[Warning] Failed to initialize Groq client: {e}")
    else:
        print("[Warning] GROQ_API_KEY not found in environment. No fallbacks available.")

    try:
        # 1. Try Gemini
        result = primary_structured.invoke(prompt_value.to_messages())
        return [apply_student_eligibility_and_scam_guards(j, profile, raw_text) for j in result.jobs]
    except Exception as primary_e:
        if not fallbacks_structured:
            raise primary_e
            
        print(f"[Fallback] Gemini hit an error (likely rate limit). Truncating text and routing to Groq...")
        
        # 2. Rebuild the prompt specifically for Groq with tighter truncation (~8k tokens)
        groq_prompt_value = evaluation_prompt.format_prompt(
            student_context=student_context,
            directive=ai_directive or "No strict directive available.",
            schedule=schedule_str,
            raw_text=raw_text[:12000],
            link_dict=link_dict[:8000],
            source_url=source_url,
            source_name=source_name
        )
        
        try:
            # 3. Try Groq
            groq_result = fallbacks_structured[0].invoke(groq_prompt_value.to_messages())
            return [apply_student_eligibility_and_scam_guards(j, profile, raw_text) for j in groq_result.jobs]
        except groq.BadRequestError as bad_req_e:
            print("[Warning] Groq refused tool call (likely 0 jobs found)")
            return []
        except Exception as groq_e:
            print(f"\n[CRITICAL GROQ ERROR] Fallback failed: {str(groq_e)}\n")
            raise groq_e # Raise the actual Groq error so it's visible in the console

def _extract_llm_text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict) and 'text' in p:
                parts.append(p['text'])
        return "".join(parts).strip()
    return str(content).strip()

def generate_cold_outreach(opportunity: dict, profile: dict) -> str:
    """
    Generates a personalized, punchy 3-sentence recruiter cold DM / email pitch
    highlighting the candidate's exact project alignment with the target role.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    resume_sample = profile.get('raw_resume_text') or profile.get('resume_text') or ''
    candidate_name = resume_sample.split('\n')[0].strip() if resume_sample else "Om Ingle"

    prompt = f"""
You are an expert technical career coach. Draft a punchy, highly professional, 3-to-4 sentence cold outreach DM (for LinkedIn or Email) to a hiring manager or recruiter.

Candidate Profile:
- Name: {candidate_name}
- Background & Projects:
{resume_sample[:1500]}

Target Opportunity:
- Role: {opportunity.get('title')}
- Company: {opportunity.get('company')}
- Key Pros / Alignment: {opportunity.get('pros')}
- Description: {opportunity.get('description', '')[:500]}

Guidelines:
1. Max 85 words.
2. Hook them with 1 specific project or skill (e.g. CropGuard AI, ExamVault, Python/ML) that directly solves a need for this role.
3. Express crisp enthusiasm for {opportunity.get('company')}.
4. Conclude with a clear, polite call-to-action (e.g. "Would you be open to a brief 5-minute chat, or may I send over my resume?").
5. Return ONLY the message text without greetings like "Subject:" or quotes.
"""

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key, temperature=0.3)
        res = llm.invoke(prompt)
        return _extract_llm_text(res.content)
    except Exception as gemini_err:
        print(f"[Cold Outreach] Gemini call failed ({gemini_err}), falling back to Groq...")
        if groq_key:
            groq_llm = ChatGroq(model="openai/gpt-oss-120b", api_key=groq_key, temperature=0.3)
            res = groq_llm.invoke(prompt)
            return _extract_llm_text(res.content)
        raise gemini_err

def generate_prep_analysis(opportunity: dict, profile: dict) -> dict:
    """
    Compares the student's resume & degree against the role/exam to produce
    structured matching strengths, missing skills/topics, and a prep checklist.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    resume_sample = (profile.get('raw_resume_text') or profile.get('resume_text') or '')[:2000]
    degree = profile.get('degree_branch') or 'B.E. / B.Tech'
    batch = profile.get('graduation_batch') or '2027'

    prompt = f"""
You are an expert technical mentor for university students.
Analyze this opportunity against the student's background and return a structured Prep & Skill-Gap plan.

Student Profile:
- Batch: {batch} | Degree/Branch: {degree}
- Resume Context:
{resume_sample or 'No resume text provided; infer based on CS/IT student background.'}

Opportunity:
- Title: {opportunity.get('title')}
- Company/Organizer: {opportunity.get('company')}
- Category: {opportunity.get('category')}
- Tags: {opportunity.get('tags')}
- Description: {opportunity.get('description', '')[:800]}

If Category is 'Exam', focus missing_skills_or_topics and prep_checklist on syllabus topics, exam pattern, and eligibility documents.
If Category is 'Job'/'Internship'/'Hackathon', focus on resume keywords, DSA/system skills, and project alignment.
"""

    try:
        llm = ChatGoogleGenerativeAI(model="gemini-3.6-flash", google_api_key=api_key, temperature=0.2)
        structured = llm.with_structured_output(PrepAnalysis)
        res = structured.invoke(prompt)
        return res.model_dump()
    except Exception as gemini_err:
        print(f"[Prep Analysis] Gemini failed ({gemini_err}), falling back to Groq...")
        if groq_key:
            groq_llm = ChatGroq(model="openai/gpt-oss-120b", api_key=groq_key, temperature=0.2)
            structured_groq = groq_llm.with_structured_output(PrepAnalysis)
            res = structured_groq.invoke(prompt)
            return res.model_dump()
        raise gemini_err
