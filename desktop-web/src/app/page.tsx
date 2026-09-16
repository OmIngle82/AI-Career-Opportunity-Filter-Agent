"use client";

import { useEffect, useState } from "react";
import { fetchOpportunities, Opportunity, API_BASE_URL } from "@/lib/api";
import OpportunityCard from "@/components/OpportunityCard";
import AddSourceModal from "@/components/AddSourceModal";
import { Loader2, RefreshCw, Plus, Play, Settings } from "lucide-react";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";

export default function Dashboard() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [activeFilter, setActiveFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await fetch(`${API_BASE_URL}/sync-sources`, { method: "POST" });
      showToast("Sync started in the background!");
      setTimeout(() => {
        loadData();
        setSyncing(false);
      }, 3000);
    } catch (e) {
      console.error(e);
      setSyncing(false);
    }
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities();
      setOpportunities(data);
    } catch (err: any) {
      console.error("Failed to load opportunities:", err);
      setError("Failed to connect to the backend server. Please ensure the FastAPI backend is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Setup Supabase Realtime
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
    if (!supabaseUrl || !supabaseKey) return;

    const supabase = createClient(supabaseUrl, supabaseKey);

    const channel = supabase.channel('custom-insert-channel')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'opportunities' }, (payload) => {
        setOpportunities((prev) => [payload.new as Opportunity, ...prev]);
        showToast("New opportunity discovered!");
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[#0f172a] text-slate-100 p-8">
      <div className="max-w-7xl mx-auto">
        <header className="flex items-center justify-between mb-12">
          <div>
            <h1 className="text-4xl font-extrabold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
              AI Career Filter
            </h1>
            <p className="text-slate-400 mt-2">
              Your personalized, AI-scored opportunities dashboard.
            </p>
          </div>
          
          <div className="flex items-center gap-3">
            <Link 
              href="/profile"
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl transition-all border border-slate-700 shadow-lg"
            >
              <Settings className="w-4 h-4" />
              Profile & Preferences
            </Link>
            <button 
              onClick={() => setIsModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-lg shadow-indigo-500/20"
            >
              <Plus className="w-4 h-4" />
              Add Source
            </button>
            <button 
              onClick={handleSync}
              disabled={syncing}
              className="flex items-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Sync Jobs
            </button>
            <button 
              onClick={loadData}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl transition-all border border-slate-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-indigo-400" : ""}`} />
              Refresh Feed
            </button>
          </div>
        </header>

        <AddSourceModal 
          isOpen={isModalOpen} 
          onClose={() => setIsModalOpen(false)} 
          onSuccess={() => {
            // Optional: You could fetch sources here if you had a sources tab
            // For now, it just closes the modal successfully.
          }} 
        />

        {/* Filter Bar */}
        <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2 scrollbar-hide">
          {['All', 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'].map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
                activeFilter === f
                  ? "bg-indigo-500 text-white shadow-lg shadow-indigo-500/30"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              {f === 'All' ? 'All Opportunities' : f + 's'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400">
            <Loader2 className="w-12 h-12 animate-spin text-indigo-500 mb-4" />
            <p>Fetching latest evaluated opportunities...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-red-400 border border-dashed border-red-900/50 rounded-3xl bg-red-950/20">
            <p className="text-lg font-semibold">Error Loading Feed</p>
            <p className="text-sm mt-2">{error}</p>
          </div>
        ) : opportunities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-400 border border-dashed border-slate-700 rounded-3xl bg-slate-800/30">
            <p className="text-lg">No opportunities found.</p>
            <p className="text-sm mt-2">Try changing your filter or start the ingestion scrapers.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
            {opportunities
              .filter(opp => activeFilter === 'All' || (opp.category || 'Other') === activeFilter)
              .map((opp) => (
                <OpportunityCard key={opp.id} opportunity={opp} />
            ))}
          </div>
        )}
      </div>

      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 bg-emerald-600 text-white px-6 py-3 rounded-lg shadow-xl shadow-emerald-900/50 flex items-center gap-3 animate-in fade-in slide-in-from-bottom-4 duration-300">
          <Play className="w-4 h-4" />
          <span className="font-medium">{toastMessage}</span>
        </div>
      )}
    </div>
  );
}
