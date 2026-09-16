import { Opportunity } from "@/lib/api";
import { AlertTriangle, CheckCircle2, XCircle, ExternalLink } from "lucide-react";

interface Props {
  opportunity: Opportunity;
}

export default function OpportunityCard({ opportunity }: Props) {
  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-400 bg-emerald-400/10 border-emerald-400/20";
    if (score >= 50) return "text-amber-400 bg-amber-400/10 border-amber-400/20";
    return "text-rose-400 bg-rose-400/10 border-rose-400/20";
  };

  return (
    <div className="flex flex-col bg-slate-800/50 backdrop-blur-md border border-slate-700/50 rounded-2xl p-6 hover:bg-slate-800/80 transition-all duration-300 shadow-xl shadow-black/20">
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1 pr-4">
          {opportunity.category && (
            <span className="inline-block px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 text-xs font-bold uppercase tracking-wider mb-2 border border-indigo-500/20">
              {opportunity.category}
            </span>
          )}
          <h3 className="text-xl font-semibold text-slate-100 leading-tight mb-1">
            {opportunity.title}
          </h3>
          <p className="text-slate-400 text-sm font-medium">
            {opportunity.company}
          </p>
        </div>
        
        <div className={`flex flex-col items-center justify-center w-16 h-16 rounded-xl border-2 ${getScoreColor(opportunity.match_score)}`}>
          <span className="text-2xl font-bold">{opportunity.match_score}</span>
          <span className="text-[10px] font-semibold uppercase tracking-wider opacity-80">Match</span>
        </div>
      </div>

      <div className="flex-1 mb-6">
        <p className="text-slate-300 text-sm line-clamp-3 leading-relaxed">
          {opportunity.description}
        </p>
      </div>

      <div className="space-y-4 mb-6">
        {opportunity.schedule_conflict && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <p><strong>Schedule Conflict:</strong> {opportunity.schedule_conflict_reason}</p>
          </div>
        )}

        <div className="space-y-2">
          {opportunity.pros && opportunity.pros.slice(0, 2).map((pro, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-emerald-300/90">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <p className="leading-snug">{pro}</p>
            </div>
          ))}
          {opportunity.cons && opportunity.cons.slice(0, 1).map((con, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-rose-300/90">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <p className="leading-snug">{con}</p>
            </div>
          ))}
        </div>
      </div>

      {opportunity.tags && opportunity.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          {opportunity.tags.map((tag, i) => (
            <span key={i} className="px-2.5 py-1 bg-slate-700/50 text-indigo-300 text-xs font-medium rounded-md border border-slate-600/50">
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto pt-4 border-t border-slate-700/50 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className="px-2 py-1 rounded-md bg-slate-800 border border-slate-700">
            Trust Score: {opportunity.legitimacy_score}/100
          </span>
        </div>
        
        <a 
          href={opportunity.apply_url || opportunity.source_url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-500 hover:bg-indigo-400 rounded-lg transition-colors shadow-lg shadow-indigo-500/20"
        >
          {opportunity.apply_url ? "Apply Now" : "View Source Page"} <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  );
}
