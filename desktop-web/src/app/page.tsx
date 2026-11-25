"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchOpportunities, Opportunity, apiFetch } from "@/lib/api";
import OpportunityCard from "@/components/OpportunityCard";
import AddSourceModal from "@/components/AddSourceModal";
import { ThemeToggle } from "@/components/ThemeToggle";
import { 
  Loader2, 
  RefreshCw, 
  Plus, 
  Settings, 
  Bot, 
  LogOut, 
  Inbox, 
  Bookmark, 
  CheckCircle2, 
  Archive, 
  Layers,
  Timer
} from "lucide-react";
import Link from "next/link";
import { createClient } from "@supabase/supabase-js";
import { toast } from "sonner";
import { useAuth } from "@/lib/AuthContext";

type StatusTab = 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED' | 'ALL';

export default function Dashboard() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [activeStatusTab, setActiveStatusTab] = useState<StatusTab>('INBOX');
  const [activeFilter, setActiveFilter] = useState('All');
  const [closingSoonOnly, setClosingSoonOnly] = useState(false);
  const [includeLowMatches, setIncludeLowMatches] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [isCrawling, setIsCrawling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { username, logout } = useAuth();

  const handleStatusChange = (id: string, newStatus: 'INBOX' | 'SAVED' | 'APPLIED' | 'DISMISSED') => {
    setOpportunities((prev) =>
      prev.map((opp) => (opp.id === id ? { ...opp, status: newStatus } : opp))
    );
  };

  const handleSync = async () => {
    setIsSyncing(true);
    toast.promise(
      apiFetch(`/sync-sources`, { method: "POST" }).then(() => {
        setTimeout(() => {
          loadData(includeLowMatches);
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
      await apiFetch(`/search/run-agentic-search`, { method: "POST" });
      toast.success('Deep Crawl complete!');
      loadData(includeLowMatches);
    } catch (e) {
      console.error(e);
      toast.error('Deep Crawl failed to connect to backend.');
    } finally {
      setIsCrawling(false);
    }
  };

  const loadData = useCallback(async (lowMatches: boolean) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities(lowMatches);
      setOpportunities(data);
    } catch (err: unknown) {
      console.error("Failed to load opportunities:", err);
      setError("Failed to connect to the backend server. Please ensure the FastAPI backend is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(includeLowMatches);
  }, [includeLowMatches, loadData]);

  useEffect(() => {
    // Setup Supabase Realtime
    const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
    const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
    if (!supabaseUrl || !supabaseKey) return;

    const supabase = createClient(supabaseUrl, supabaseKey);

    const channel = supabase.channel('custom-insert-channel')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'opportunities' }, (payload: { new: Opportunity }) => {
        setOpportunities((prev) => [payload.new, ...prev]);
        toast.success("New opportunity discovered!");
      })
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="min-h-screen p-3 sm:p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        <header className="flex items-center justify-between gap-3 mb-4 md:mb-10 sticky top-0 bg-slate-50/90 dark:bg-slate-950/90 backdrop-blur-xl z-20 py-3 md:py-4 border-b border-slate-200 dark:border-slate-800 -mx-3 px-3 sm:-mx-4 sm:px-4 md:mx-0 md:px-0">
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl md:text-4xl font-extrabold bg-gradient-to-r from-indigo-500 to-cyan-500 bg-clip-text text-transparent truncate">
              AI Career Filter
            </h1>
            <p className="hidden sm:block text-slate-500 dark:text-slate-400 mt-1 md:mt-2 text-xs md:text-base">
              Your personalized, AI-scored opportunities dashboard.
            </p>
          </div>
          
          {/* Mobile Compact Header Controls */}
          <div className="flex md:hidden items-center gap-1.5 shrink-0">
            <ThemeToggle />
            <Link 
              href="/profile"
              className="p-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm"
              aria-label="Preferences"
              title="Preferences"
            >
              <Settings className="w-4 h-4" />
            </Link>
            <button
              onClick={logout}
              className="p-2 bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:text-red-500 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm"
              aria-label="Logout"
              title={`Logout (${username || 'User'})`}
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>

          {/* Desktop Full Header Controls */}
          <div className="hidden md:flex flex-wrap items-center gap-3">
            <ThemeToggle />

            <Link 
              href="/profile"
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl transition-all border border-slate-200 dark:border-slate-700 shadow-sm"
            >
              <Settings className="w-4 h-4" />
              <span>Preferences</span>
            </Link>
            <button 
              onClick={() => setIsModalOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 rounded-xl transition-all border border-slate-200 dark:border-slate-700 shadow-sm"
            >
              <Plus className="w-4 h-4" />
              <span>Add Source</span>
            </button>
            <button 
              onClick={handleSync}
              disabled={isSyncing}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-sm shadow-emerald-500/20 disabled:opacity-50"
            >
              {isSyncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              <span>Sync</span>
            </button>
            <button 
              onClick={handleDeepCrawl}
              disabled={isCrawling}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-sm shadow-indigo-500/20 disabled:opacity-50"
            >
              {isCrawling ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bot className="w-4 h-4" />}
              <span>Deep Crawl</span>
            </button>
            <div className="flex items-center gap-2 border-l border-slate-200 dark:border-slate-700 pl-3 ml-1">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">
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
        </header>

        {/* Mobile Non-Sticky Action Bar */}
        <div className="grid grid-cols-3 gap-2 mb-5 md:hidden">
          <button 
            onClick={() => setIsModalOpen(true)}
            className="flex items-center justify-center gap-1.5 px-2.5 py-2.5 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200 rounded-xl transition-all border border-slate-200 dark:border-slate-800 shadow-sm text-xs font-semibold"
          >
            <Plus className="w-3.5 h-3.5 shrink-0" />
            <span className="truncate">Add Source</span>
          </button>
          <button 
            onClick={handleSync}
            disabled={isSyncing}
            className="flex items-center justify-center gap-1.5 px-2.5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl transition-all shadow-sm shadow-emerald-500/20 disabled:opacity-50 text-xs font-semibold"
          >
            {isSyncing ? <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" /> : <RefreshCw className="w-3.5 h-3.5 shrink-0" />}
            <span>Sync</span>
          </button>
          <button 
            onClick={handleDeepCrawl}
            disabled={isCrawling}
            className="flex items-center justify-center gap-1.5 px-2.5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl transition-all shadow-sm shadow-indigo-500/20 disabled:opacity-50 text-xs font-semibold"
          >
            {isCrawling ? <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" /> : <Bot className="w-3.5 h-3.5 shrink-0" />}
            <span className="truncate">Deep Crawl</span>
          </button>
        </div>

        <AddSourceModal 
          isOpen={isModalOpen} 
          onClose={() => setIsModalOpen(false)} 
          onSuccess={() => {}} 
        />

        {/* ATS Status Navigation Tabs */}
        {(() => {
          const statusTabs: { id: StatusTab; label: string; icon: React.ComponentType<{ className?: string }>; count: number; badgeColor: string }[] = [
            {
              id: 'INBOX',
              label: 'Inbox',
              icon: Inbox,
              count: opportunities.filter(o => !o.status || o.status === 'INBOX').length,
              badgeColor: 'bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800'
            },
            {
              id: 'SAVED',
              label: 'Saved',
              icon: Bookmark,
              count: opportunities.filter(o => o.status === 'SAVED').length,
              badgeColor: 'bg-amber-100 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-800'
            },
            {
              id: 'APPLIED',
              label: 'Applied',
              icon: CheckCircle2,
              count: opportunities.filter(o => o.status === 'APPLIED').length,
              badgeColor: 'bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800'
            },
            {
              id: 'DISMISSED',
              label: 'Archived',
              icon: Archive,
              count: opportunities.filter(o => o.status === 'DISMISSED').length,
              badgeColor: 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700'
            },
            {
              id: 'ALL',
              label: 'All Leads',
              icon: Layers,
              count: opportunities.length,
              badgeColor: 'bg-cyan-100 dark:bg-cyan-950/60 text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-800'
            }
          ];

          const filteredOpportunities = opportunities
            .filter((opp) => {
              const oppStatus = opp.status || 'INBOX';
              if (activeStatusTab !== 'ALL' && oppStatus !== activeStatusTab) {
                return false;
              }
              if (activeFilter !== 'All' && (opp.category || 'Other') !== activeFilter) {
                return false;
              }
              if (closingSoonOnly && !opp.application_deadline) {
                return false;
              }
              return true;
            })
            .sort((a, b) => {
              if (!closingSoonOnly) return 0;
              const da = a.application_deadline ? new Date(a.application_deadline).getTime() : Number.MAX_SAFE_INTEGER;
              const db = b.application_deadline ? new Date(b.application_deadline).getTime() : Number.MAX_SAFE_INTEGER;
              return da - db;
            });

          return (
            <>
              {/* ATS Primary Status Tabs */}
              <div className="flex items-center gap-1.5 sm:gap-2 mb-3 sm:mb-4 overflow-x-auto pb-2 scrollbar-hide border-b border-slate-200 dark:border-slate-800 -mx-3 px-3 sm:mx-0 sm:px-0">
                {statusTabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeStatusTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveStatusTab(tab.id)}
                      className={`flex items-center gap-1.5 sm:gap-2 px-3 sm:px-3.5 py-1.5 sm:py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all whitespace-nowrap shrink-0 ${
                        isActive
                          ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-sm"
                          : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800/60"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
                      <span>{tab.label}</span>
                      <span
                        className={`text-[11px] sm:text-xs px-1.5 sm:px-2 py-0.5 rounded-full font-bold border ${
                          isActive
                            ? "bg-white/20 dark:bg-slate-900/20 text-current border-transparent"
                            : tab.badgeColor
                        }`}
                      >
                        {tab.count}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Category Filter Pills & Student Controls */}
              <div className="flex items-center gap-1.5 sm:gap-2 mb-6 sm:mb-8 overflow-x-auto pb-2 scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
                {['All', 'Job', 'Internship', 'Exam', 'Hackathon', 'Other'].map((f) => (
                  <button
                    key={f}
                    onClick={() => setActiveFilter(f)}
                    className={`px-3 sm:px-3.5 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap shrink-0 border ${
                      activeFilter === f
                        ? "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-700 dark:text-indigo-400 border-indigo-200 dark:border-indigo-500/20 shadow-sm"
                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                    }`}
                  >
                    {f === 'All' ? 'All Types' : f + 's'}
                  </button>
                ))}
                <button
                  onClick={() => setClosingSoonOnly((v) => !v)}
                  className={`inline-flex items-center gap-1 px-3 sm:px-3.5 py-1 rounded-full text-xs font-semibold transition-all whitespace-nowrap shrink-0 border ${
                    closingSoonOnly
                      ? "bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300 border-amber-300 dark:border-amber-700 shadow-sm"
                      : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                >
                  <Timer className="w-3 h-3" />
                  <span>Closing Soon</span>
                </button>
                <button
                  onClick={() => setIncludeLowMatches((v) => !v)}
                  className={`px-3 sm:px-3.5 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap shrink-0 border ${
                    includeLowMatches
                      ? "bg-slate-800 text-white dark:bg-slate-200 dark:text-slate-900 border-transparent"
                      : "bg-white dark:bg-slate-900 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                  }`}
                >
                  {includeLowMatches ? "Showing <60 Matches" : "Include <60 Matches"}
                </button>
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
              ) : filteredOpportunities.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-500 dark:text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-3xl bg-white dark:bg-slate-900/30 px-6">
                  {activeStatusTab === 'INBOX' && (
                    <>
                      <Inbox className="w-10 h-10 text-slate-400 mb-3" />
                      <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">Your Inbox is Clear</p>
                      <p className="text-sm mt-1 text-center max-w-sm text-slate-500 dark:text-slate-400">
                        All new leads have been reviewed or triaged. Check your <b>Saved</b> or <b>Applied</b> tabs, or trigger a <b>Sync</b> or <b>Deep Crawl</b>.
                      </p>
                    </>
                  )}
                  {activeStatusTab === 'SAVED' && (
                    <>
                      <Bookmark className="w-10 h-10 text-amber-500 mb-3" />
                      <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">No Saved Opportunities</p>
                      <p className="text-sm mt-1 text-center max-w-sm text-slate-500 dark:text-slate-400">
                        Star any opportunity in your Inbox by clicking the bookmark icon to review and apply to it later.
                      </p>
                    </>
                  )}
                  {activeStatusTab === 'APPLIED' && (
                    <>
                      <CheckCircle2 className="w-10 h-10 text-emerald-500 mb-3" />
                      <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">No Applications Tracked Yet</p>
                      <p className="text-sm mt-1 text-center max-w-sm text-slate-500 dark:text-slate-400">
                        When you apply for a job or internship, click <b>Mark Applied</b> on its card to track it here.
                      </p>
                    </>
                  )}
                  {activeStatusTab === 'DISMISSED' && (
                    <>
                      <Archive className="w-10 h-10 text-slate-400 mb-3" />
                      <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">No Archived Opportunities</p>
                      <p className="text-sm mt-1 text-center max-w-sm text-slate-500 dark:text-slate-400">
                        Dismissed opportunities will be kept here and automatically purged after 30 days.
                      </p>
                    </>
                  )}
                  {activeStatusTab === 'ALL' && (
                    <>
                      <p className="text-lg font-semibold text-slate-700 dark:text-slate-300">No opportunities found</p>
                      <p className="text-sm mt-2 text-center max-w-sm text-slate-500 dark:text-slate-400">
                        Try changing your category filter, or trigger a Sync or Deep Crawl to fetch new data.
                      </p>
                    </>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 sm:gap-4 lg:gap-6">
                  {filteredOpportunities.map((opp) => (
                    <OpportunityCard 
                      key={opp.id} 
                      opportunity={opp} 
                      onStatusChange={handleStatusChange} 
                    />
                  ))}
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}
