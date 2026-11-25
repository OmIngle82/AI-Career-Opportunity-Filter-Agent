"use client";

import { useState } from "react";
import { Opportunity, PrepAnalysis, updateOpportunityStatus, generateColdOutreach, generatePrepAnalysis } from "@/lib/api";
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ExternalLink,
  Clock,
  Calendar,
  Bookmark,
  Check,
  Archive,
  Sparkles,
  Copy,
  CheckCheck,
  Loader2,
  ShieldCheck,
  GraduationCap,
  Timer
} from "lucide-react";
import { toast } from "sonner";

interface Props {
  opportunity: Opportunity;
  onStatusChange?: (id: string, newStatus: 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED') => void;
}

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return "Just now";

    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay === 1) return "Yesterday";
    if (diffDay < 7) return `${diffDay}d ago`;
    if (diffDay < 30) return `${Math.floor(diffDay / 7)}w ago`;

    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return "";
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: date.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined
    });
  } catch {
    return "";
  }
}

export default function OpportunityCard({ opportunity, onStatusChange }: Props) {
  const [currentStatus, setCurrentStatus] = useState<'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED'>(
    opportunity.status || 'INBOX'
  );
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [showPitch, setShowPitch] = useState(false);
  const [pitchDraft, setPitchDraft] = useState<string | null>(opportunity.cold_outreach_draft || null);
  const [isGeneratingPitch, setIsGeneratingPitch] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showPrep, setShowPrep] = useState(false);
  const [prepData, setPrepData] = useState<PrepAnalysis | null>(opportunity.prep_analysis || null);
  const [isGeneratingPrep, setIsGeneratingPrep] = useState(false);

  const [nowMs] = useState(() => Date.now());

  const getDeadlineInfo = (deadlineStr?: string | null) => {
    if (!deadlineStr) return null;
    try {
      const target = new Date(deadlineStr);
      if (isNaN(target.getTime())) return null;
      const diffDays = Math.ceil((target.getTime() - nowMs) / (1000 * 60 * 60 * 24));
      if (diffDays < 0) return { label: "Expired", urgent: "expired" as const };
      if (diffDays === 0) return { label: "Closes Today", urgent: "critical" as const };
      if (diffDays <= 5) return { label: `Closes in ${diffDays}d`, urgent: "soon" as const };
      return {
        label: `Due ${target.toLocaleDateString(undefined, { month: "short", day: "numeric" })}`,
        urgent: "normal" as const,
      };
    } catch {
      return null;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800";
    if (score >= 70) return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800";
    return "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-200 dark:border-slate-700";
  };

  const handleStatusUpdate = async (newStatus: 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED') => {
    const prev = currentStatus;
    const targetStatus = prev === newStatus ? 'INBOX' : newStatus;
    setCurrentStatus(targetStatus);
    setIsUpdatingStatus(true);

    try {
      await updateOpportunityStatus(opportunity.id, targetStatus);
      if (onStatusChange) {
        onStatusChange(opportunity.id, targetStatus);
      }
      const label = targetStatus === 'SAVED' ? 'Saved to Bookmarks' : targetStatus === 'APPLIED' ? 'Marked as Applied' : targetStatus === 'DISMISSED' ? 'Archived' : 'Moved to Inbox';
      toast.success(label);
    } catch {
      setCurrentStatus(prev);
      toast.error("Failed to update status");
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  const handleGeneratePitch = async () => {
    if (pitchDraft) {
      setShowPitch(!showPitch);
      return;
    }

    setShowPitch(true);
    setIsGeneratingPitch(true);
    try {
      const draft = await generateColdOutreach(opportunity.id);
      setPitchDraft(draft);
      toast.success("Tailored recruiter pitch generated!");
    } catch {
      toast.error("Could not generate pitch");
    } finally {
      setIsGeneratingPitch(false);
    }
  };

  const handleCopyPitch = () => {
    if (!pitchDraft) return;
    navigator.clipboard.writeText(pitchDraft);
    setCopied(true);
    toast.success("Copied to clipboard!");
    setTimeout(() => setCopied(false), 2500);
  };

  const handleGeneratePrep = async () => {
    if (prepData) {
      setShowPrep(!showPrep);
      return;
    }
    setShowPrep(true);
    setIsGeneratingPrep(true);
    try {
      const prep = await generatePrepAnalysis(opportunity.id);
      setPrepData(prep);
      toast.success("Prep & Skill-Gap plan ready!");
    } catch {
      toast.error("Could not generate prep analysis");
    } finally {
      setIsGeneratingPrep(false);
    }
  };

  const relativeTime = opportunity.created_at ? formatRelativeTime(opportunity.created_at) : "";
  const fullDateStr = opportunity.created_at ? new Date(opportunity.created_at).toLocaleString() : "";
  const shortDate = opportunity.created_at ? formatDate(opportunity.created_at) : "";
  const deadlineInfo = getDeadlineInfo(opportunity.application_deadline);
  const examDateFormatted = opportunity.exam_date ? formatDate(opportunity.exam_date) : "";

  return (
    <div className="flex flex-col bg-white dark:bg-slate-900 rounded-2xl shadow-sm hover:shadow-md transition-all duration-200 border border-slate-200/80 dark:border-slate-800 p-4 sm:p-5 relative overflow-hidden">

      {/* Top Header */}
      <div className="flex justify-between items-start mb-3 sm:mb-4 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-2">
            {opportunity.category && (
              <span className="inline-block px-2 sm:px-2.5 py-0.5 rounded-full bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 text-[10px] sm:text-xs font-bold uppercase tracking-wider border border-indigo-100 dark:border-indigo-500/20">
                {opportunity.category}
              </span>
            )}
            {relativeTime && (
              <span
                className="inline-flex items-center gap-1 text-[11px] sm:text-xs text-slate-500 dark:text-slate-400 font-medium bg-slate-50 dark:bg-slate-800/80 px-2 py-0.5 rounded-full border border-slate-200/60 dark:border-slate-700/60"
                title={`Discovered on ${fullDateStr}`}
              >
                <Clock className="w-3 h-3 text-slate-400 dark:text-slate-500" />
                {relativeTime}
              </span>
            )}
            {deadlineInfo && (
              <span
                className={`inline-flex items-center gap-1 text-[11px] sm:text-xs font-bold px-2 py-0.5 rounded-full border ${
                  deadlineInfo.urgent === 'critical' || deadlineInfo.urgent === 'expired'
                    ? 'bg-rose-50 dark:bg-rose-950/50 text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-800'
                    : deadlineInfo.urgent === 'soon'
                    ? 'bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
                    : 'bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700'
                }`}
              >
                <Timer className="w-3 h-3" />
                {deadlineInfo.label}
              </span>
            )}
            {examDateFormatted && (
              <span className="inline-flex items-center gap-1 text-[11px] sm:text-xs font-semibold px-2 py-0.5 rounded-full bg-cyan-50 dark:bg-cyan-950/40 text-cyan-700 dark:text-cyan-300 border border-cyan-200 dark:border-cyan-800">
                Exam: {examDateFormatted}
              </span>
            )}
          </div>
          <h3 className="text-base sm:text-lg font-bold text-slate-900 dark:text-slate-100 leading-tight mb-1 line-clamp-2">
            {opportunity.title}
          </h3>
          <p className="text-slate-600 dark:text-slate-400 text-xs sm:text-sm font-semibold truncate">
            {opportunity.company}
          </p>
        </div>

        {/* Score Badge */}
        <div className={`flex flex-col items-center justify-center w-12 h-12 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl border shrink-0 ${getScoreColor(opportunity.match_score)}`}>
          <span className="text-lg sm:text-xl font-black leading-none">{opportunity.match_score}</span>
          <span className="text-[8px] sm:text-[9px] font-bold uppercase tracking-wider opacity-80 mt-0.5">Match</span>
        </div>
      </div>

      {/* Description */}
      <div className="flex-1 mb-4">
        <p className="text-slate-600 dark:text-slate-300 text-sm line-clamp-3 leading-relaxed">
          {opportunity.description}
        </p>
      </div>

      {/* Conflicts & Pros */}
      <div className="space-y-2.5 mb-4">
        {opportunity.schedule_conflict && (
          <div className="flex items-start gap-2 p-2.5 rounded-xl bg-rose-50 dark:bg-rose-500/10 border border-rose-100 dark:border-rose-500/20 text-rose-700 dark:text-rose-300 text-xs">
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <p><strong>Conflict:</strong> {opportunity.schedule_conflict_reason}</p>
          </div>
        )}

        <div className="space-y-1.5">
          {opportunity.pros && opportunity.pros.slice(0, 2).map((pro, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <p className="leading-snug">{pro}</p>
            </div>
          ))}
          {opportunity.cons && opportunity.cons.slice(0, 1).map((con, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-rose-700 dark:text-rose-400">
              <XCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <p className="leading-snug">{con}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Tags & Student Meta */}
      {(opportunity.tags?.length || opportunity.stipend_or_ctc || opportunity.eligible_batches?.length) ? (
        <div className="flex flex-wrap gap-1.5 mb-4">
          {opportunity.stipend_or_ctc && (
            <span className="px-2 py-0.5 bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 text-[11px] font-semibold rounded-md border border-emerald-200 dark:border-emerald-800">
              {opportunity.stipend_or_ctc}
            </span>
          )}
          {opportunity.eligible_batches && opportunity.eligible_batches.length > 0 && (
            <span className="px-2 py-0.5 bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 text-[11px] font-semibold rounded-md border border-amber-200 dark:border-amber-800">
              Batch: {opportunity.eligible_batches.join(', ')}
            </span>
          )}
          {opportunity.tags && opportunity.tags.map((tag, i) => (
            <span key={i} className="px-2 py-0.5 bg-slate-50 dark:bg-slate-800 text-indigo-600 dark:text-indigo-300 text-[11px] font-medium rounded-md border border-slate-200/80 dark:border-slate-700">
              #{tag}
            </span>
          ))}
        </div>
      ) : null}

      {/* Prep & Skill-Gap Expandable Section */}
      {showPrep && (
        <div className="mb-4 p-3 sm:p-3.5 rounded-xl bg-emerald-50/70 dark:bg-emerald-950/25 border border-emerald-200 dark:border-emerald-800/50 transition-all">
          <div className="flex items-center gap-1.5 text-xs font-bold text-emerald-900 dark:text-emerald-300 mb-2">
            <GraduationCap className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
            <span>Prep &amp; Skill-Gap Plan</span>
          </div>
          {isGeneratingPrep ? (
            <div className="flex items-center justify-center py-4 text-xs text-emerald-700 dark:text-emerald-400 gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Comparing against your resume...</span>
            </div>
          ) : prepData ? (
            <div className="space-y-2.5 text-xs text-slate-700 dark:text-slate-300">
              <p className="font-medium text-emerald-800 dark:text-emerald-300">{prepData.estimated_prep_focus}</p>
              {prepData.matching_strengths?.length > 0 && (
                <div>
                  <span className="font-semibold text-emerald-700 dark:text-emerald-400">Your Strengths: </span>
                  {prepData.matching_strengths.join(' • ')}
                </div>
              )}
              {prepData.missing_skills_or_topics?.length > 0 && (
                <div>
                  <span className="font-semibold text-amber-700 dark:text-amber-400">Brush Up On: </span>
                  {prepData.missing_skills_or_topics.join(' • ')}
                </div>
              )}
              {prepData.prep_checklist?.length > 0 && (
                <ul className="list-disc pl-4 space-y-0.5 text-[11px]">
                  {prepData.prep_checklist.map((step, idx) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* AI Pitch Expandable Section */}
      {showPitch && (
        <div className="mb-4 p-3 sm:p-3.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/50 transition-all">
          <div className="flex items-center justify-between gap-2 mb-2">
            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-900 dark:text-indigo-300">
              <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
              <span className="sm:hidden">Recruiter Pitch</span>
              <span className="hidden sm:inline">Tailored Recruiter Pitch (LinkedIn / Email)</span>
            </span>
            {pitchDraft && (
              <button
                onClick={handleCopyPitch}
                className="inline-flex items-center gap-1 px-2 py-1 text-xs font-semibold text-indigo-700 dark:text-indigo-300 bg-white dark:bg-slate-800 hover:bg-indigo-100 dark:hover:bg-indigo-900/50 rounded-lg border border-indigo-200 dark:border-indigo-700 transition-colors shadow-2xs"
                title="Copy to clipboard"
              >
                {copied ? <CheckCheck className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                <span>{copied ? "Copied" : "Copy"}</span>
              </button>
            )}
          </div>

          {isGeneratingPitch ? (
            <div className="flex items-center justify-center py-4 text-xs text-indigo-600 dark:text-indigo-400 gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing resume & drafting outreach with Gemini...</span>
            </div>
          ) : (
            <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed italic bg-white/60 dark:bg-slate-900/60 p-2.5 rounded-lg border border-indigo-100 dark:border-indigo-900/30">
              &ldquo;{pitchDraft}&rdquo;
            </p>
          )}
        </div>
      )}

      {/* Action Toolbar & Footer */}
      <div className="mt-auto pt-3 border-t border-slate-100 dark:border-slate-800 flex flex-col gap-3">

        {/* Quick ATS Status Actions */}
        <div className="flex flex-col gap-1.5 bg-slate-50 dark:bg-slate-800/60 p-1.5 rounded-xl border border-slate-200/60 dark:border-slate-700/60">
          <div className="grid grid-cols-3 gap-1">
            <button
              onClick={() => handleStatusUpdate('SAVED')}
              disabled={isUpdatingStatus}
              className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all min-w-0 ${currentStatus === 'SAVED'
                ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-800 dark:text-amber-300 border border-amber-300 dark:border-amber-700'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-700'
                }`}
              title="Bookmark / Save opportunity"
            >
              <Bookmark className={`w-3.5 h-3.5 shrink-0 ${currentStatus === 'SAVED' ? 'fill-current' : ''}`} />
              <span className="truncate">Save</span>
            </button>

            <button
              onClick={() => handleStatusUpdate('APPLIED')}
              disabled={isUpdatingStatus}
              className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all min-w-0 ${currentStatus === 'APPLIED'
                ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-700'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-700'
                }`}
              title="Mark as Applied"
            >
              <Check className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Applied</span>
            </button>

            <button
              onClick={() => handleStatusUpdate('DISMISSED')}
              disabled={isUpdatingStatus}
              className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all min-w-0 ${currentStatus === 'DISMISSED'
                ? 'bg-rose-100 dark:bg-rose-900/40 text-rose-800 dark:text-rose-300 border border-rose-300 dark:border-rose-700'
                : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200/60 dark:hover:bg-slate-700'
                }`}
              title="Dismiss / Archive opportunity"
            >
              <Archive className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Dismiss</span>
            </button>
          </div>

          <div className="grid grid-cols-2 gap-1 pt-1 border-t border-slate-200/60 dark:border-slate-700/60">
            {/* Prep & Skill-Gap Trigger */}
            <button
              onClick={handleGeneratePrep}
              className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all min-w-0 ${showPrep
                ? 'bg-emerald-600 text-white'
                : 'text-emerald-700 dark:text-emerald-400 bg-white/70 dark:bg-slate-900/50 hover:bg-emerald-50 dark:hover:bg-emerald-950/50 border border-emerald-200/60 dark:border-emerald-800/40'
                }`}
              title="Prep & Skill-Gap analysis"
            >
              <GraduationCap className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Prep &amp; Gap</span>
            </button>

            {/* AI Pitch Trigger */}
            <button
              onClick={handleGeneratePitch}
              className={`flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg text-xs font-semibold transition-all min-w-0 ${showPitch
                ? 'bg-indigo-600 text-white'
                : 'text-indigo-600 dark:text-indigo-400 bg-white/70 dark:bg-slate-900/50 hover:bg-indigo-50 dark:hover:bg-indigo-950/50 border border-indigo-200/60 dark:border-indigo-800/40'
                }`}
              title="Generate AI tailored recruiter cold pitch"
            >
              <Sparkles className="w-3.5 h-3.5 shrink-0" />
              <span className="truncate">Outreach</span>
            </button>
          </div>
        </div>

        {/* Footer Meta & Apply Button */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-2.5 pt-1">
          <div className="flex flex-wrap items-center justify-between sm:justify-start gap-1.5 text-xs text-slate-500 dark:text-slate-400">
            <span className="px-2 py-0.5 rounded-md bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700">
              Trust: {opportunity.legitimacy_score}/100
            </span>
            {opportunity.is_official_source ? (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 text-emerald-700 dark:text-emerald-300 font-medium">
                <ShieldCheck className="w-3 h-3" /> Official Portal
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded-md bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400">
                Aggregator
              </span>
            )}
            {shortDate && (
              <span
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-slate-50 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-500 dark:text-slate-400"
                title={`Discovered on ${fullDateStr}`}
              >
                <Calendar className="w-3 h-3 text-slate-400" />
                {shortDate}
              </span>
            )}
          </div>

          <a
            href={opportunity.apply_url || opportunity.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 px-4 py-2.5 sm:py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 dark:bg-indigo-500 dark:hover:bg-indigo-400 rounded-xl transition-all shadow-sm active:scale-98 w-full sm:w-auto"
          >
            {opportunity.apply_url ? "Apply Now" : "View Source"} <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

      </div>
    </div>
  );
}
