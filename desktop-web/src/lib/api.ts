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
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

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
    window.location.href = "/login";
  }

  return res;
}

export async function fetchOpportunities(): Promise<Opportunity[]> {
  try {
    const res = await apiFetch(`/opportunities`, {
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
