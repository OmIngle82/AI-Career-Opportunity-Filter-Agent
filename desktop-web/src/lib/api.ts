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

export async function fetchOpportunities(): Promise<Opportunity[]> {
  try {
    const res = await fetch(`${API_BASE_URL}/opportunities`, {
      cache: "no-store", // disable caching for live data
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
