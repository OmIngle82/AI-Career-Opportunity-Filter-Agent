import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from models import OpportunityEvaluation, ProfileSynthesis, OpportunityEvaluations
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable
from langchain_google_genai.chat_models import GoogleAPIError
from langchain_groq import ChatGroq
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

# Removed retry decorator to manually manage rate limit rotation
def extract_and_evaluate_opportunities(raw_text: str, link_dict: str, profile: dict, schedule: list, source_url: str, source_name: str) -> list[OpportunityEvaluation]:
    ai_directive = profile.get("ai_filter_directive")
    schedule_str = "\\n".join([f"- {s.get('event_name')}: {s.get('start_date')} to {s.get('end_date')}" for s in schedule])
    if not schedule_str:
        schedule_str = "No upcoming schedule constraints."

    evaluation_prompt = PromptTemplate.from_template("""
    You are an expert career counselor and cybersecurity AI. Your goal is to simultaneously EXTRACT and EVALUATE the top 3 career opportunities (jobs, internships, exams) from the provided raw text.
    
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

    INSTRUCTIONS:
    1. Extract up to 3 high-quality career opportunities found in the Raw Page Text.
    2. For EACH opportunity, select the exact Absolute Application URL from the 'JSON Link Dictionary'. This is mandatory.
       PRIORITIZE: When extracting the apply_url for an Exam or Government Job, prioritize official domains (.gov.in, .nic.in, .ac.in, .edu.in) over aggregator or news domains whenever multiple links are present.
    3. Evaluate EACH opportunity based on the STRICT AI FILTER DIRECTIVE.
    4. Provide a match_score (0-100), legitimacy_score (0-100), fraud_risk_score (0-100), credibility_flags, pros, and cons.
    5. strictly classify the opportunity into one of the allowed categories: 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'.
       EXAM DEFINITION: 'Exam' must ONLY be used for official government/PSU recruitment notifications, official university exam registrations, or official hackathons.
       COMMERCIAL COURSE FILTER: If the text is promoting a commercial coaching course, mock test series, bootcamp, or tutorial (e.g., a GeeksforGeeks GATE prep course), you MUST set the category to 'Other' and penalize the match_score heavily (below 30), or reject it entirely. We only want the actual opportunities, not the preparation courses.
    6. Extract 3-4 short, highly relevant tags (e.g., tech stack like 'Next.js', work mode like 'Remote', or exam name like 'GATE').
    7. If the text mentions 'Government Job' but the URL is not .gov.in or .nic.in, flag it and increase fraud risk.
    8. Recognize official exam notices and government bulletins as valid opportunities. Extract deadlines and eligibility.
    """)
    
    prompt_value = evaluation_prompt.format_prompt(
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
            groq_client = Groq(api_key=groq_key)
            available_models = groq_client.models.list().data
            # Find the best Llama model dynamically (prefer 70b, then 3.1, then anything Llama)
            valid_models = [m.id for m in available_models if "llama" in m.id.lower()]

            if valid_models:
                # Sort to prefer versatile/70b models if they exist
                best_model = next((m for m in valid_models if "70b" in m), valid_models[0])
                print(f"[Groq] Dynamically selected model: {best_model}")

                groq_llm = ChatGroq(
                    model=best_model,
                    api_key=groq_key,
                    temperature=0.1,
                )
                fallbacks_structured.append(groq_llm.with_structured_output(OpportunityEvaluations))
        except Exception as e:
            print(f"[Warning] Failed to dynamically fetch Groq models: {e}")
    else:
        print("[Warning] GROQ_API_KEY not found in environment. No fallbacks available.")

    try:
        # 1. Try Gemini
        result = primary_structured.invoke(prompt_value.to_messages())
        return result.jobs
    except Exception as primary_e:
        if not fallbacks_structured:
            raise primary_e
            
        print(f"[Fallback] Gemini hit an error (likely rate limit). Truncating text and routing to Groq...")
        
        # 2. Rebuild the prompt specifically for Groq with tighter truncation (~8k tokens)
        groq_prompt_value = evaluation_prompt.format_prompt(
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
            return groq_result.jobs
        except Exception as groq_e:
            print(f"\n[CRITICAL GROQ ERROR] Fallback failed: {str(groq_e)}\n")
            raise groq_e # Raise the actual Groq error so it's visible in the console
