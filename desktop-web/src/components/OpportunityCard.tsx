import { Opportunity } from "@/lib/api";
import { AlertTriangle, CheckCircle2, XCircle, ExternalLink } from "lucide-react";

interface Props {
  opportunity: Opportunity;
}

export default function OpportunityCard({ opportunity }: Props) {
  const getScoreColor = (score: number) => {
    if (score >= 85) return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800";
    if (score >= 70) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800";
    return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
  };

  return (
    <div className="flex flex-col bg-white dark:bg-slate-900 rounded-xl shadow-sm hover:shadow-md transition-shadow duration-200 border border-slate-100 dark:border-slate-800 p-5">
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1 pr-4">
          {opportunity.category && (
            <span className="inline-block px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 text-xs font-bold uppercase tracking-wider mb-2 border border-indigo-100 dark:border-indigo-500/20">
              {opportunity.category}
            </span>
          )}
          <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100 leading-tight mb-1">
            {opportunity.title}
          </h3>
          <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">
            {opportunity.company}
          </p>
        </div>
        
        <div className={`flex flex-col items-center justify-center w-14 h-14 rounded-xl border ${getScoreColor(opportunity.match_score)}`}>
          <span className="text-xl font-bold">{opportunity.match_score}</span>
          <span className="text-[9px] font-semibold uppercase tracking-wider opacity-80">Match</span>
        </div>
      </div>

      <div className="flex-1 mb-5">
        <p className="text-slate-600 dark:text-slate-300 text-sm line-clamp-3 leading-relaxed">
          {opportunity.description}
        </p>
      </div>

      <div className="space-y-3 mb-5">
        {opportunity.schedule_conflict && (
          <div className="flex items-start gap-2 p-3 rounded-lg bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-sm">
            <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
            <p><strong>Schedule Conflict:</strong> {opportunity.schedule_conflict_reason}</p>
          </div>
        )}

        <div className="space-y-1.5">
          {opportunity.pros && opportunity.pros.slice(0, 2).map((pro, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <p className="leading-snug">{pro}</p>
            </div>
          ))}
          {opportunity.cons && opportunity.cons.slice(0, 1).map((con, i) => (
            <div key={i} className="flex items-start gap-2 text-sm text-rose-700 dark:text-rose-400">
              <XCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <p className="leading-snug">{con}</p>
            </div>
          ))}
        </div>
      </div>

      {opportunity.tags && opportunity.tags.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          {opportunity.tags.map((tag, i) => (
            <span key={i} className="px-2.5 py-1 bg-slate-50 dark:bg-slate-800 text-indigo-600 dark:text-indigo-300 text-xs font-medium rounded-md border border-slate-200 dark:border-slate-700">
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-auto pt-4 border-t border-slate-100 dark:border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
          <span className="px-2 py-1 rounded-md bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
            Trust Score: {opportunity.legitimacy_score}/100
          </span>
        </div>
        
        <a 
          href={opportunity.apply_url || opportunity.source_url} 
          target="_blank" 
          rel="noopener noreferrer"
          className="w-full md:w-auto flex items-center justify-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400 rounded-lg transition-colors shadow-sm"
        >
          {opportunity.apply_url ? "Apply Now" : "View Source"} <ExternalLink className="w-4 h-4" />
        </a>
      </div>
    </div>
  );
}
