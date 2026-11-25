export interface PrepAnalysis {
  matching_strengths: string[];
  missing_skills_or_topics: string[];
  prep_checklist: string[];
  estimated_prep_focus: string;
}

export interface Opportunity {
  id: string;
  title: string;
  company: string;
  description: string;
  source_url: string;
  apply_url?: string;
  match_score: number;
  schedule_conflict: boolean;
  schedule_conflict_reason: string;
  legitimacy_score: number;
  pros: string[];
  cons: string[];
  category?: string;
  tags?: string[];
  raw_text: string;
  created_at: string;
  status?: 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED';
  cold_outreach_draft?: string;
  application_deadline?: string | null;
  exam_date?: string | null;
  stipend_or_ctc?: string | null;
  eligible_batches?: string[] | null;
  is_official_source?: boolean;
  prep_analysis?: PrepAnalysis | null;
}

export const API_BASE_URL = 
  process.env.NEXT_PUBLIC_API_URL || 
  (typeof window !== "undefined" && (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
    ? "http://localhost:8000"
    : "https://ai-career-opportunity-filter-agent.onrender.com");

// A wrapper for fetch that automatically adds auth headers and handles 401s
export async function apiFetch(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers || {});
  
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }
  }

  const res = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("token");
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.href = "/login";
  }

  return res;
}

export async function fetchOpportunities(includeLowMatches = false): Promise<Opportunity[]> {
  try {
    const res = await apiFetch(`/opportunities?include_low_matches=${includeLowMatches}`, {
      cache: "no-store", 
      signal: AbortSignal.timeout(15000)
    });
    
    if (!res.ok) {
      throw new Error(`Failed to fetch opportunities: ${res.statusText}`);
    }
    
    const data = await res.json();
    return data.opportunities || [];
  } catch (error) {
    console.error("Error fetching opportunities:", error);
    throw error;
  }
}

export async function updateOpportunityStatus(
  id: string, 
  status: 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED'
): Promise<Opportunity> {
  const res = await apiFetch(`/opportunities/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
  if (!res.ok) throw new Error("Failed to update status");
  const data = await res.json();
  return data.opportunity;
}

export async function generateColdOutreach(id: string): Promise<string> {
  const res = await apiFetch(`/opportunities/${id}/generate-outreach`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to generate outreach pitch");
  const data = await res.json();
  return data.draft;
}

export async function generatePrepAnalysis(id: string): Promise<PrepAnalysis> {
  const res = await apiFetch(`/opportunities/${id}/prep`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Failed to generate prep analysis");
  const data = await res.json();
  return data.prep;
}
