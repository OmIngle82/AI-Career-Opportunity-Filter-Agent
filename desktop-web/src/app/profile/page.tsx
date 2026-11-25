"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { UploadCloud, Bot, Loader2, Sparkles, Check, Send, ArrowLeft, LogOut } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/AuthContext";
import { ThemeToggle } from "@/components/ThemeToggle";
import { toast } from "sonner";

export default function ProfilePage() {
  const [preferences, setPreferences] = useState({
    roles: "",
    tech_stack: "",
    locations: "",
    work_modes: "",
    min_salary: "",
    active_commitments: "",
    target_exams: ""
  });
  const [graduationBatch, setGraduationBatch] = useState("2027");
  const [degreeBranch, setDegreeBranch] = useState("B.E. IT/CS");
  const [experienceLevel, setExperienceLevel] = useState("Student / Fresher (0-1 yr)");
  const [targetExamTracks, setTargetExamTracks] = useState<string[]>(["GATE", "TCS NQT", "ISRO / DRDO / BARC"]);
  const [telegramChatId, setTelegramChatId] = useState("");
  const [minAlertScore, setMinAlertScore] = useState(60);
  const [dailyDigestEnabled, setDailyDigestEnabled] = useState(true);
  const [rawResumeText, setRawResumeText] = useState("");
  
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  // Modal & AI State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { username, logout } = useAuth();
  
  const [synthesis, setSynthesis] = useState<{ summary: string[], directive: string }>({ summary: [], directive: "" });
  const [feedback, setFeedback] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadProfile = async () => {
    try {
      const res = await apiFetch(`/profile`);
      if (res.ok) {
        const data = await res.json();
        setPreferences(data.form_preferences || {
          roles: "", tech_stack: "", locations: "", work_modes: "", min_salary: "", active_commitments: "", target_exams: ""
        });
        setGraduationBatch(data.graduation_batch || "2027");
        setDegreeBranch(data.degree_branch || "B.E. IT/CS");
        setExperienceLevel(data.experience_level || "Student / Fresher (0-1 yr)");
        setTargetExamTracks(Array.isArray(data.target_exam_tracks) && data.target_exam_tracks.length > 0 ? data.target_exam_tracks : ["GATE", "TCS NQT"]);
        setTelegramChatId(data.telegram_chat_id || "");
        setMinAlertScore(typeof data.min_alert_score === "number" ? data.min_alert_score : 60);
        setDailyDigestEnabled(typeof data.daily_digest_enabled === "boolean" ? data.daily_digest_enabled : true);
        setRawResumeText(data.raw_resume_text || "");
        if (data.ai_filter_directive) {
          setSynthesis({ summary: data.summary, directive: data.ai_filter_directive });
        }
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadProfile();
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await apiFetch(`/profile/upload-resume`, {
        method: "POST",
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setRawResumeText(data.extracted_text);
        toast.success("Resume successfully extracted!");
      } else {
        const err = await res.json();
        toast.error(`Upload failed: ${err.detail || "Unknown error"}`);
      }
    } catch (err) {
      console.error(err);
      toast.error("Error uploading file.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleGenerateDirective = async () => {
    setIsModalOpen(true);
    setIsSynthesizing(true);
    
    try {
      const res = await apiFetch(`/profile/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preferences: {
            ...preferences,
            graduation_batch: graduationBatch,
            degree_branch: degreeBranch,
            experience_level: experienceLevel,
            target_exam_tracks: targetExamTracks,
          },
          resume_text: rawResumeText
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSynthesis(data);
      } else {
        toast.error("Error synthesizing profile.");
        setIsModalOpen(false);
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error.");
      setIsModalOpen(false);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleRefine = async () => {
    if (!feedback.trim()) return;
    setIsRefining(true);
    
    try {
      const res = await apiFetch(`/profile/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_summary: synthesis.summary,
          current_directive: synthesis.directive,
          feedback: feedback
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSynthesis(data);
        setFeedback("");
      } else {
        toast.error("Error refining directive.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error.");
    } finally {
      setIsRefining(false);
    }
  };

  const handleConfirmAndActivate = async () => {
    setIsSaving(true);
    try {
      const res = await apiFetch(`/profile/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          form_preferences: preferences,
          raw_resume_text: rawResumeText,
          ai_filter_directive: synthesis.directive,
          graduation_batch: graduationBatch,
          degree_branch: degreeBranch,
          experience_level: experienceLevel,
          target_exam_tracks: targetExamTracks,
          telegram_chat_id: telegramChatId,
          min_alert_score: minAlertScore,
          daily_digest_enabled: dailyDigestEnabled,
        })
      });
      if (res.ok) {
        toast.success("AI Persona Compiled & Activated!");
        setIsModalOpen(false);
      } else {
        toast.error("Error saving profile.");
      }
    } catch (err) {
      console.error(err);
      toast.error("Network error.");
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-500 dark:text-slate-400"><Loader2 className="animate-spin w-8 h-8" /></div>;

  return (
    <div className="min-h-screen">
      <nav className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-950/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-2xl mx-auto px-4 md:px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link 
              href="/" 
              className="p-2 -ml-2 rounded-lg text-slate-500 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Back to Dashboard"
            >
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <span className="font-semibold text-slate-900 dark:text-slate-100 tracking-tight">AI Persona Compiler</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            <div className="flex items-center gap-2 border-l border-slate-200 dark:border-slate-700 pl-2 sm:pl-3">
              <span className="hidden sm:inline text-sm font-medium text-slate-700 dark:text-slate-300">
                {username}
              </span>
              <button
                onClick={logout}
                className="p-2 text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-2xl mx-auto px-4 md:px-6 py-10 pb-32">
        <div className="mb-8">
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white mb-2">Profile Preferences</h1>
          <p className="text-slate-500 dark:text-slate-400">Define your precise constraints. Gemini Flash will compile these into a strict directive.</p>
        </div>

        <div className="space-y-6 sm:space-y-8">
          {/* Student Eligibility & Exam Radar */}
          <section className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl shadow-sm p-4 sm:p-6">
            <h2 className="text-lg sm:text-xl font-semibold text-slate-900 dark:text-slate-100 mb-1">Student Eligibility &amp; Exam Radar</h2>
            <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mb-5">Used to automatically reject wrong graduation batches &amp; 2+ yr senior roles.</p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-5">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Graduation Batch</label>
                <select value={graduationBatch} onChange={(e) => setGraduationBatch(e.target.value)} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm text-slate-900 dark:text-slate-100">
                  {["2025", "2026", "2027", "2028", "2029"].map((yr) => (
                    <option key={yr} value={yr}>{yr} Batch</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Degree &amp; Branch</label>
                <input type="text" value={degreeBranch} onChange={(e) => setDegreeBranch(e.target.value)} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm text-slate-900 dark:text-slate-100" placeholder="e.g. B.E. IT/CS" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Experience Level</label>
                <select value={experienceLevel} onChange={(e) => setExperienceLevel(e.target.value)} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm text-slate-900 dark:text-slate-100">
                  <option value="Student / Fresher (0-1 yr)">Student / Fresher (0-1 yr)</option>
                  <option value="Internship Only">Internship Only</option>
                  <option value="0-2 Years">0-2 Years</option>
                </select>
              </div>
            </div>

            <div className="mb-5">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Target Exam &amp; Drive Tracks</label>
              <div className="flex flex-wrap gap-2">
                {["GATE", "TCS NQT", "ISRO / DRDO / BARC", "NIC / NIELIT", "Infosys HackWithInfy", "Off-Campus Hackathons"].map((track) => {
                  const selected = targetExamTracks.includes(track);
                  return (
                    <button
                      type="button"
                      key={track}
                      onClick={() =>
                        setTargetExamTracks((prev) =>
                          prev.includes(track) ? prev.filter((t) => t !== track) : [...prev, track]
                        )
                      }
                      className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition-all ${
                        selected
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-xs"
                          : "bg-slate-50 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:bg-slate-100"
                      }`}
                    >
                      {track}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-slate-100 dark:border-slate-800">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Telegram Chat ID</label>
                <input type="text" value={telegramChatId} onChange={(e) => setTelegramChatId(e.target.value)} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm text-slate-900 dark:text-slate-100" placeholder="e.g. 1220500210" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Min Telegram Alert Score</label>
                <select value={minAlertScore} onChange={(e) => setMinAlertScore(Number(e.target.value))} className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm text-slate-900 dark:text-slate-100">
                  <option value={50}>50+ (Broad)</option>
                  <option value={60}>60+ (Recommended)</option>
                  <option value={75}>75+ (High Match Only)</option>
                </select>
              </div>
              <div className="flex items-end pb-1">
                <label className="inline-flex items-center gap-2.5 cursor-pointer text-sm font-medium text-slate-700 dark:text-slate-300">
                  <input type="checkbox" checked={dailyDigestEnabled} onChange={(e) => setDailyDigestEnabled(e.target.checked)} className="w-4 h-4 rounded text-indigo-600" />
                  Daily Morning Digest
                </label>
              </div>
            </div>
          </section>

          {/* Career & Roles */}
          <section className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl shadow-sm p-6">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Career & Roles</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Target Titles</label>
                <input type="text" value={preferences.roles || ""} onChange={(e) => setPreferences({ ...preferences, roles: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. SDE, Data Analyst, Product Manager" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Tech Stack / Skills</label>
                <input type="text" value={preferences.tech_stack || ""} onChange={(e) => setPreferences({ ...preferences, tech_stack: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. React, Python, SQL" />
              </div>
            </div>
          </section>

          {/* Location & Work Mode */}
          <section className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl shadow-sm p-6">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Location & Work Mode</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Preferred Cities</label>
                <input type="text" value={preferences.locations || ""} onChange={(e) => setPreferences({ ...preferences, locations: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. Pune, Bangalore, Delhi" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Work Modes</label>
                <input type="text" value={preferences.work_modes || ""} onChange={(e) => setPreferences({ ...preferences, work_modes: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. Remote Only, Hybrid acceptable" />
              </div>
            </div>
          </section>

          {/* Commitments & Comp */}
          <section className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl shadow-sm p-6">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-6">Commitments & Compensation</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Min Salary</label>
                <input type="text" value={preferences.min_salary || ""} onChange={(e) => setPreferences({ ...preferences, min_salary: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. 50k INR/month" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Active Commitments</label>
                <input type="text" value={preferences.active_commitments || ""} onChange={(e) => setPreferences({ ...preferences, active_commitments: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. Full-time Student" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Target Exams</label>
                <input type="text" value={preferences.target_exams || ""} onChange={(e) => setPreferences({ ...preferences, target_exams: e.target.value })} className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500" placeholder="e.g. UPSC, GATE 2027" />
              </div>
            </div>
          </section>

          {/* Resume Upload */}
          <section className="bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 rounded-xl shadow-sm p-6">
            <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100 mb-2">Resume Context</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">Upload your PDF resume. We&apos;ll parse it so the AI knows exactly what you&apos;ve done.</p>
            
            <div 
              className="border-2 border-dashed border-slate-200 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-500 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-50 dark:bg-slate-800/50 mb-6"
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="w-10 h-10 text-indigo-500 mb-3" />
              <p className="text-slate-700 dark:text-slate-300 font-medium">{uploading ? "Parsing..." : "Click to Upload PDF Resume"}</p>
              <p className="text-slate-400 dark:text-slate-500 text-sm mt-1">PyMuPDF will instantly extract text</p>
              <input type="file" accept=".pdf" className="hidden" ref={fileInputRef} onChange={handleFileUpload} />
            </div>

            {rawResumeText && (
              <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-4">
                <p className="text-xs font-semibold text-indigo-500 mb-2 uppercase tracking-wider">Extracted Raw Text</p>
                <div className="h-40 overflow-y-auto text-xs text-slate-600 dark:text-slate-400 font-mono whitespace-pre-wrap pr-4 custom-scrollbar">
                  {rawResumeText}
                </div>
              </div>
            )}
          </section>
        </div>

        {/* Floating Action Button */}
        <div className="fixed bottom-0 left-0 right-0 p-4 md:p-6 bg-gradient-to-t from-slate-50 via-slate-50 dark:from-slate-950 dark:via-slate-950 to-transparent flex justify-center z-30 pointer-events-none">
          <button
            onClick={handleGenerateDirective}
            className="pointer-events-auto flex items-center justify-center gap-2 w-full max-w-sm md:w-auto md:px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl md:rounded-full font-bold shadow-lg shadow-indigo-600/20 transition-all hover:-translate-y-1"
          >
            <Sparkles className="w-5 h-5" />
            Generate AI Directive
          </button>
        </div>
      </main>
      
      {/* AI Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => !isSynthesizing && setIsModalOpen(false)}></div>
          
          <div className="relative w-full max-w-3xl bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 shadow-2xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {isSynthesizing ? (
              <div className="flex flex-col items-center justify-center p-8 sm:p-20 text-indigo-500">
                <Bot className="w-12 h-12 sm:w-16 sm:h-16 mb-4 sm:mb-6 animate-pulse" />
                <h3 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white mb-2 text-center">Compiling Persona</h3>
                <p className="text-slate-500 dark:text-slate-400 text-center text-sm max-w-md">Gemini Flash is analyzing your preferences and resume to build a strict filtering directive...</p>
              </div>
            ) : (
              <>
                <div className="p-4 sm:p-6 border-b border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
                  <h3 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Bot className="w-5 h-5 text-indigo-500" />
                    AI Persona Compiled
                  </h3>
                </div>
                
                <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5 sm:space-y-6">
                  <div>
                    <h4 className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 mb-2 uppercase tracking-wider">Human Summary</h4>
                    <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 rounded-lg p-3.5 sm:p-4 text-slate-700 dark:text-slate-300 text-xs sm:text-sm leading-relaxed">
                      {Array.isArray(synthesis.summary) ? synthesis.summary.map((para, i) => (
                        <p key={i} className="mb-3 last:mb-0">{para}</p>
                      )) : <p>{synthesis.summary}</p>}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-xs sm:text-sm font-semibold text-rose-600 dark:text-rose-400 mb-2 uppercase tracking-wider">Strict AI Directive</h4>
                    <div className="bg-slate-50 dark:bg-slate-950 border border-rose-200 dark:border-rose-900/30 rounded-lg p-3.5 sm:p-4 text-slate-700 dark:text-slate-300 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-mono">
                      {synthesis.directive}
                    </div>
                  </div>
                </div>

                <div className="p-4 sm:p-6 border-t border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-900/50">
                  <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 mb-3 sm:mb-4">
                    <input 
                      type="text" 
                      value={feedback}
                      onChange={e => setFeedback(e.target.value)}
                      placeholder="Make an adjustment... (e.g. 'Allow entry-level roles')"
                      className="flex-1 bg-transparent border border-slate-200 dark:border-slate-700 rounded-xl px-3.5 sm:px-4 py-2.5 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                      onKeyDown={e => e.key === 'Enter' && handleRefine()}
                    />
                    <button 
                      onClick={handleRefine}
                      disabled={isRefining || !feedback.trim()}
                      className="px-4 py-2.5 bg-slate-200 hover:bg-slate-300 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-900 dark:text-white rounded-xl transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-sm font-medium border border-slate-300 dark:border-slate-700"
                    >
                      {isRefining ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      Refine
                    </button>
                  </div>
                  
                  <button
                    onClick={handleConfirmAndActivate}
                    disabled={isSaving}
                    className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all shadow-md flex items-center justify-center gap-2"
                  >
                    {isSaving ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
                    Confirm & Activate Filter
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
