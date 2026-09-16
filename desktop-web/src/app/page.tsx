"use client";

import { useEffect, useState } from "react";
import { fetchOpportunities, Opportunity, API_BASE_URL } from "@/lib/api";
import OpportunityCard from "@/components/OpportunityCard";
import AddSourceModal from "@/components/AddSourceModal";
import { Loader2, RefreshCw, Plus, Settings, Bot } from "lucide-react";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { toast } from "sonner";

export default function Dashboard() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [activeFilter, setActiveFilter] = useState('All');
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCrawling, setIsCrawling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSync = async () => {
    setIsSyncing(true);
    toast.promise(
      fetch(`${API_BASE_URL}/sync-sources`, { method: "POST" }).then(() => {
        setTimeout(() => {
          loadData();
          setIsSyncing(false);
        }, 3000);
      }),
      {
        loading: 'Sync started in the background...',
        success: 'Sync complete! Refreshing...',
        error: 'Sync failed'
      }
    );
  };

  const handleDeepCrawl = async () => {
    setIsCrawling(true);
    toast.info('Agentic Deep Crawl initiated. This may take a few minutes...');
    try {
      await fetch(`${API_BASE_URL}/search/run-agentic-search`, { method: "POST" });
      toast.success('Deep Crawl complete!');
      loadData();
    } catch (e) {
      console.error(e);
      toast.error('Deep Crawl failed to connect to backend.');
    } finally {
      setIsCrawling(false);
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
        toast.success("New opportunity discovered!");
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="min-h-screen p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-6 mb-10 sticky top-0 bg-slate-50/80 dark:bg-slate-950/80 backdrop-blur-xl z-10 py-4 border-b border-slate-200 dark:border-slate-800">
          <div>
            <h1 className="text-3xl md:text-4xl font-extrabold bg-gradient-to-r from-indigo-500 to-cyan-500 bg-clip-text text-transparent">
              AI Career Filter
            </h1>
            <p className="text-slate-500 dark:text-slate-400 mt-1 md:mt-2 text-sm md:text-base">
              Your personalized, AI-scored opportunities dashboard.
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-3">
            <Link 
              href="/profile"
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl transition-all border border-slate-200 dark:border-slate-700 shadow-sm flex-1 md:flex-none"
            >
              <Settings className="w-4 h-4" />
              <span className="hidden md:inline">Preferences</span>
            </Link>
            <button 
              onClick={() => setIsModalOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl transition-all border border-slate-200 dark:border-slate-700 shadow-sm flex-1 md:flex-none"
            >
              <Plus className="w-4 h-4" />
              <span className="hidden md:inline">Add Source</span>
            </button>
            <button 
              onClick={handleSync}
              disabled={isSyncing}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-sm shadow-emerald-500/20 disabled:opacity-50 flex-1 md:flex-none"
            >
              {isSyncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              <span>Sync</span>
            </button>
            <button 
              onClick={handleDeepCrawl}
              disabled={isCrawling}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-sm shadow-indigo-500/20 disabled:opacity-50 flex-1 md:flex-none"
            >
              {isCrawling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
              <span>Deep Crawl</span>
            </button>
          </div>
        </header>

        <AddSourceModal 
          isOpen={isModalOpen} 
          onClose={() => setIsModalOpen(false)} 
          onSuccess={() => {}} 
        />

        {/* Filter Bar */}
        <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-2 scrollbar-hide">
          {['All', 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'].map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all whitespace-nowrap border ${
                activeFilter === f
                  ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20 shadow-sm"
                  : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
              }`}
            >
              {f === 'All' ? 'All Opportunities' : f + 's'}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400">
            <Loader2 className="w-10 h-10 animate-spin text-indigo-500 mb-4" />
            <p>Fetching latest evaluated opportunities...</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-20 text-rose-600 dark:text-rose-400 border border-dashed border-rose-200 dark:border-rose-900/50 rounded-3xl bg-rose-50 dark:bg-rose-950/20">
            <p className="text-lg font-semibold">Error Loading Feed</p>
            <p className="text-sm mt-2">{error}</p>
          </div>
        ) : opportunities.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-3xl bg-white dark:bg-slate-900/30">
            <p className="text-lg">No opportunities found.</p>
            <p className="text-sm mt-2 text-center max-w-sm">Try changing your filter, or trigger a Sync or Deep Crawl to fetch new data.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 lg:gap-6">
            {opportunities
              .filter(opp => activeFilter === 'All' || (opp.category || 'Other') === activeFilter)
              .map((opp) => (
                <OpportunityCard key={opp.id} opportunity={opp} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
