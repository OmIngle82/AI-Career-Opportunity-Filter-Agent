from pydantic import BaseModel, Field
from typing import List, Optional

class UserProfile(BaseModel):
    user_id: str
    # Legacy fields
    goals: Optional[str] = None
    preferred_stipend_min: Optional[int] = None
    learning_focus: Optional[str] = None
    resume_text: Optional[str] = None
    target_locations: Optional[str] = None
    tech_stack: Optional[str] = None
    active_commitments: Optional[str] = None

    # V2 fields
    raw_resume_text: Optional[str] = None
    form_preferences: Optional[dict] = None
    ai_filter_directive: Optional[str] = None

class FormPreferences(BaseModel):
    roles: Optional[str] = None
    tech_stack: Optional[str] = None
    locations: Optional[str] = None
    work_modes: Optional[str] = None
    min_salary: Optional[str] = None
    active_commitments: Optional[str] = None
    target_exams: Optional[str] = None

class ProfileSynthesis(BaseModel):
    summary: List[str] = Field(description="A concise human-readable summary of the user's career profile, returned as exactly 3 distinct strings/paragraphs.")
    directive: str = Field(description="A strict, robust filtering directive outlining how AI should score and flag opportunities for this user.")

class UserSchedule(BaseModel):
    event_name: str
    start_date: str
    end_date: str

class OpportunityInput(BaseModel):
    raw_text: str
    source_url: Optional[str] = None
    apply_url: Optional[str] = None
    source_name: str = "Unknown"
    source_tier: str = "TIER_2_GENERIC"

class OpportunityEvaluation(BaseModel):
    title: str = Field(description="The title of the job or opportunity.")
    company: str = Field(description="The company or organization offering the opportunity.")
    description: str = Field(description="A brief summary of the opportunity.")
    category: str = Field(description="Must be strictly one of: 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'")
    tags: List[str] = Field(description="Maximum 4 short descriptive tags (e.g., 'Next.js', 'Remote', 'GATE')")
    apply_url: Optional[str] = Field(description="The exact absolute application URL strictly selected from the provided JSON Link Dictionary.", default=None)
    match_score: int = Field(description="An integer score from 0 to 100 indicating how well this matches the user profile.")
    schedule_conflict: bool = Field(description="True if the opportunity conflicts with the user's schedule.")
    schedule_conflict_reason: str = Field(description="Explanation of the schedule conflict, if any.")
    legitimacy_score: int = Field(description="An integer score from 0 to 100 assessing the legitimacy of the opportunity.")
    fraud_risk_score: int = Field(description="An integer score from 0 to 100 assessing the probability that this is a scam or fake listing.")
    credibility_flags: List[str] = Field(description="A list of red flags or green flags regarding the domain and legitimacy.")
    pros: List[str] = Field(description="A list of pros for this opportunity based on user goals.")
    cons: List[str] = Field(description="A list of cons for this opportunity based on user goals.")

class OpportunityEvaluations(BaseModel):
    jobs: List[OpportunityEvaluation] = Field(description="List of evaluated jobs, up to 3 max.")

class SourceInput(BaseModel):
    name: str
    url_or_identifier: str
    source_type: str
    source_tier: str
