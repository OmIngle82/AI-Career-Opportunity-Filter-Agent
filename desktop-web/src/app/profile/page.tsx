"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { UploadCloud, Bot, Loader2, Sparkles, Check, Send } from "lucide-react";
import { API_BASE_URL } from "@/lib/api";

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
  const [rawResumeText, setRawResumeText] = useState("");
  
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Modal & AI State
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  
  const [synthesis, setSynthesis] = useState<{ summary: string[], directive: string }>({ summary: [], directive: "" });
  const [feedback, setFeedback] = useState("");

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/profile`);
      if (res.ok) {
        const data = await res.json();
        setPreferences(data.form_preferences || {
          roles: "", tech_stack: "", locations: "", work_modes: "", min_salary: "", active_commitments: "", target_exams: ""
        });
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

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE_URL}/profile/upload-resume`, {
        method: "POST",
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setRawResumeText(data.extracted_text);
        showToast("Resume successfully extracted!");
      } else {
        const err = await res.json();
        showToast(`Upload failed: ${err.detail || "Unknown error"}`);
      }
    } catch (err) {
      console.error(err);
      showToast("Error uploading file.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleGenerateDirective = async () => {
    setIsModalOpen(true);
    setIsSynthesizing(true);
    
    try {
      const res = await fetch(`${API_BASE_URL}/profile/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preferences, resume_text: rawResumeText })
      });
      if (res.ok) {
        const data = await res.json();
        setSynthesis(data);
      } else {
        showToast("Error synthesizing profile.");
        setIsModalOpen(false);
      }
    } catch (err) {
      console.error(err);
      showToast("Network error.");
      setIsModalOpen(false);
    } finally {
      setIsSynthesizing(false);
    }
  };

  const handleRefine = async () => {
    if (!feedback.trim()) return;
    setIsRefining(true);
    
    try {
      const res = await fetch(`${API_BASE_URL}/profile/refine`, {
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
        showToast("Error refining directive.");
      }
    } catch (err) {
      console.error(err);
      showToast("Network error.");
    } finally {
      setIsRefining(false);
    }
  };

  const handleConfirmAndActivate = async () => {
    setIsSaving(true);
    try {
      const res = await fetch(`${API_BASE_URL}/profile/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          form_preferences: preferences,
          raw_resume_text: rawResumeText,
          ai_filter_directive: synthesis.directive
        })
      });
      if (res.ok) {
        showToast("AI Persona Compiled & Activated!");
        setIsModalOpen(false);
      } else {
        showToast("Error saving profile.");
      }
    } catch (err) {
      console.error(err);
      showToast("Network error.");
    } finally {
      setIsSaving(false);
    }
  };

  if (loading) return <div className="min-h-screen bg-slate-950 flex items-center justify-center text-slate-400"><Loader2 className="animate-spin w-8 h-8" /></div>;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans selection:bg-indigo-500/30">
      <nav className="border-b border-slate-800/50 bg-slate-900/50 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-indigo-500 to-cyan-400 flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-slate-950" />
            </div>
            <span className="font-semibold text-slate-100 tracking-tight">AI Persona Compiler</span>
          </div>
          <Link href="/" className="px-4 py-2 text-sm font-medium text-slate-400 hover:text-slate-200 transition-colors">
            &larr; Back to Dashboard
          </Link>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-10 pb-32">
        <div className="mb-10">
          <h1 className="text-4xl font-extrabold tracking-tight text-white mb-3">Profile Preferences</h1>
          <p className="text-slate-400 text-lg">Define your precise constraints. Gemini Flash will compile these into a strict directive.</p>
        </div>

        <div className="space-y-8">
          {/* Career & Roles */}
          <section className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-xl font-semibold text-white mb-6">Career & Roles</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Target Titles</label>
                <input type="text" value={preferences.roles || ""} onChange={(e) => setPreferences({ ...preferences, roles: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. SDE, Data Analyst, Product Manager" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Tech Stack / Skills</label>
                <input type="text" value={preferences.tech_stack || ""} onChange={(e) => setPreferences({ ...preferences, tech_stack: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. React, Python, SQL" />
              </div>
            </div>
          </section>

          {/* Location & Work Mode */}
          <section className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-xl font-semibold text-white mb-6">Location & Work Mode</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Preferred Cities</label>
                <input type="text" value={preferences.locations || ""} onChange={(e) => setPreferences({ ...preferences, locations: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. Pune, Bangalore, Delhi" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Work Modes</label>
                <input type="text" value={preferences.work_modes || ""} onChange={(e) => setPreferences({ ...preferences, work_modes: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. Remote Only, Hybrid acceptable" />
              </div>
            </div>
          </section>

          {/* Commitments & Comp */}
          <section className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-xl font-semibold text-white mb-6">Commitments & Compensation</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Min Salary/Stipend</label>
                <input type="text" value={preferences.min_salary || ""} onChange={(e) => setPreferences({ ...preferences, min_salary: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. 50k INR/month or 12LPA" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Active Commitments</label>
                <input type="text" value={preferences.active_commitments || ""} onChange={(e) => setPreferences({ ...preferences, active_commitments: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. Full-time Student 9-5" />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">Target Exams</label>
                <input type="text" value={preferences.target_exams || ""} onChange={(e) => setPreferences({ ...preferences, target_exams: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 transition-all" placeholder="e.g. UPSC, GATE 2027" />
              </div>
            </div>
          </section>

          {/* Resume Upload */}
          <section className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-6 backdrop-blur-sm">
            <h2 className="text-xl font-semibold text-white mb-2">Resume Context</h2>
            <p className="text-sm text-slate-400 mb-6">Upload your PDF resume. We'll parse it so the AI knows exactly what you've done.</p>
            
            <div 
              className="border-2 border-dashed border-slate-700 hover:border-indigo-500 rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-colors bg-slate-950/50 mb-6"
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud className="w-10 h-10 text-indigo-400 mb-3" />
              <p className="text-slate-300 font-medium">{uploading ? "Parsing..." : "Click to Upload PDF Resume"}</p>
              <p className="text-slate-500 text-sm mt-1">PyMuPDF will instantly extract text</p>
              <input type="file" accept=".pdf" className="hidden" ref={fileInputRef} onChange={handleFileUpload} />
            </div>

            {rawResumeText && (
              <div className="bg-slate-950 border border-slate-800 rounded-lg p-4">
                <p className="text-xs font-semibold text-indigo-400 mb-2 uppercase tracking-wider">Extracted Raw Text</p>
                <div className="h-40 overflow-y-auto text-xs text-slate-400 font-mono whitespace-pre-wrap pr-4 custom-scrollbar">
                  {rawResumeText}
                </div>
              </div>
            )}
          </section>
        </div>

        {/* Floating Action Button */}
        <div className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-slate-950 via-slate-950 to-transparent flex justify-center z-30 pointer-events-none">
          <button
            onClick={handleGenerateDirective}
            className="pointer-events-auto flex items-center gap-2 px-8 py-4 bg-indigo-600 hover:bg-indigo-500 text-white rounded-full font-bold shadow-2xl shadow-indigo-600/30 transition-all hover:-translate-y-1"
          >
            <Sparkles className="w-5 h-5" />
            Generate AI Directive
          </button>
        </div>
      </main>
      
      {/* AI Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={() => !isSynthesizing && setIsModalOpen(false)}></div>
          
          <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-700 shadow-2xl rounded-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {isSynthesizing ? (
              <div className="flex flex-col items-center justify-center p-20 text-indigo-400">
                <Bot className="w-16 h-16 mb-6 animate-pulse" />
                <h3 className="text-2xl font-bold text-white mb-2">Compiling Persona</h3>
                <p className="text-slate-400 text-center max-w-md">Gemini Flash is analyzing your preferences and resume to build a strict filtering directive...</p>
              </div>
            ) : (
              <>
                <div className="p-6 border-b border-slate-800 bg-slate-900/50">
                  <h3 className="text-xl font-bold text-white flex items-center gap-2">
                    <Bot className="w-5 h-5 text-indigo-400" />
                    AI Persona Compiled
                  </h3>
                </div>
                
                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  <div>
                    <h4 className="text-sm font-semibold text-emerald-400 mb-2 uppercase tracking-wider">Human Summary</h4>
                    <div className="bg-slate-950 border border-slate-800 rounded-lg p-4 text-slate-300 text-sm leading-relaxed">
                      {Array.isArray(synthesis.summary) ? synthesis.summary.map((para, i) => (
                        <p key={i} className="mb-4 last:mb-0">{para}</p>
                      )) : <p>{synthesis.summary}</p>}
                    </div>
                  </div>
                  
                  <div>
                    <h4 className="text-sm font-semibold text-rose-400 mb-2 uppercase tracking-wider">Strict AI Directive</h4>
                    <div className="bg-slate-950 border border-rose-900/30 rounded-lg p-4 text-slate-300 text-sm leading-relaxed whitespace-pre-wrap font-mono">
                      {synthesis.directive}
                    </div>
                  </div>
                </div>

                <div className="p-6 border-t border-slate-800 bg-slate-900/50">
                  <div className="flex gap-3 mb-4">
                    <input 
                      type="text" 
                      value={feedback}
                      onChange={e => setFeedback(e.target.value)}
                      placeholder="Make an adjustment... (e.g. 'Allow entry-level roles too')"
                      className="flex-1 bg-slate-950 border border-slate-700 rounded-xl px-4 py-2.5 text-slate-200 focus:outline-none focus:border-indigo-500 text-sm"
                      onKeyDown={e => e.key === 'Enter' && handleRefine()}
                    />
                    <button 
                      onClick={handleRefine}
                      disabled={isRefining || !feedback.trim()}
                      className="px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-white rounded-xl transition-colors disabled:opacity-50 flex items-center gap-2 text-sm font-medium border border-slate-700"
                    >
                      {isRefining ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      Refine
                    </button>
                  </div>
                  
                  <button
                    onClick={handleConfirmAndActivate}
                    disabled={isSaving}
                    className="w-full py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-bold transition-all shadow-lg shadow-indigo-600/20 flex items-center justify-center gap-2"
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

      {toastMessage && (
        <div className="fixed top-6 right-6 bg-emerald-600 text-white px-6 py-3 rounded-lg shadow-xl shadow-emerald-900/50 font-medium animate-in fade-in slide-in-from-top-4 z-[60]">
          {toastMessage}
        </div>
      )}
    </div>
  );
}
