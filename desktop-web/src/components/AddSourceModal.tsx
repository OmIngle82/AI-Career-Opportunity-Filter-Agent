import { useEffect, useState } from "react";
import { apiFetch, deleteSource, fetchSources, SourceItem, syncAtsNow, testAtsUrl, TestAtsResult } from "@/lib/api";
import { X, Plus, Loader2, CheckCircle2, RefreshCw, Trash2, FlaskConical } from "lucide-react";
import { toast } from "sonner";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

function detectAtsBadge(url: string): string | null {
  const lower = url.toLowerCase();
  if (lower.includes("myworkdayjobs.com")) return "Workday";
  if (lower.includes("greenhouse.io")) return "Greenhouse";
  if (lower.includes("lever.co")) return "Lever";
  if (lower.includes("ashbyhq.com")) return "Ashby";
  return null;
}

export default function AddSourceModal({ isOpen, onClose, onSuccess }: Props) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [type, setType] = useState("ATS");
  const [tier, setTier] = useState("TIER_1_TRUSTED");
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<TestAtsResult | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [sources, setSources] = useState<SourceItem[]>([]);
  const [syncingAts, setSyncingAts] = useState(false);

  const loadSources = async () => {
    try {
      const items = await fetchSources();
      setSources(items);
    } catch {
      // ignore initial load errors
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    fetchSources()
      .then((items) => {
        if (!cancelled) setSources(items);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const detectedPlatform = detectAtsBadge(url);

  const handleUrlChange = (val: string) => {
    setUrl(val);
    setTestResult(null);
    setTestError(null);
    if (detectAtsBadge(val)) {
      setType("ATS");
      setTier("TIER_1_TRUSTED");
    }
  };

  const handleTestUrl = async () => {
    if (!url.trim()) return;
    setTesting(true);
    setTestResult(null);
    setTestError(null);
    try {
      const res = await testAtsUrl(url.trim());
      setTestResult(res);
      if (!name.trim() && res.company) {
        setName(res.company);
      }
      toast.success(`Connected to ${res.platform.toUpperCase()} (${res.sample_count} sample jobs found)`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Could not reach ATS board";
      setTestError(msg);
      toast.error(msg);
    } finally {
      setTesting(false);
    }
  };

  const handleSyncAts = async () => {
    setSyncingAts(true);
    try {
      await syncAtsNow();
      toast.success("Direct ATS sync started in background!");
      onSuccess();
    } catch {
      toast.error("Failed to start ATS sync");
    } finally {
      setSyncingAts(false);
    }
  };

  const handleDeleteSource = async (id: string) => {
    try {
      await deleteSource(id);
      setSources((prev) => prev.filter((s) => s.id !== id));
      toast.success("Source removed");
    } catch {
      toast.error("Failed to delete source");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await apiFetch(`/sources`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          url_or_identifier: url,
          source_type: type,
          source_tier: tier,
        }),
      });

      if (res.ok) {
        setName("");
        setUrl("");
        setTestResult(null);
        await loadSources();
        toast.success("Source saved!");
        onSuccess();
      } else {
        toast.error("Failed to add source");
      }
    } catch (error) {
      console.error(error);
      toast.error("Network error while saving source");
    } finally {
      setLoading(false);
    }
  };

  const atsSources = sources.filter((s) => s.source_type === "ATS" || detectAtsBadge(s.url_or_identifier));

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-3 sm:p-4">
      <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-lg border border-slate-100 dark:border-slate-800 w-full max-w-lg p-5 sm:p-6 relative max-h-[90vh] overflow-y-auto">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-1">Add Career or ATS Source</h2>
        <p className="text-xs text-slate-500 dark:text-slate-400 mb-5">
          Paste any Workday, Greenhouse, Lever, or Ashby board URL for zero-RAM direct polling.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">URL or Identifier</label>
              {detectedPlatform && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800">
                  {detectedPlatform} Detected
                </span>
              )}
            </div>
            <div className="flex flex-col sm:flex-row gap-2">
              <input 
                type="text" 
                required
                placeholder="https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"
                value={url}
                onChange={(e) => handleUrlChange(e.target.value)}
                className="flex-1 bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
              />
              <button
                type="button"
                onClick={handleTestUrl}
                disabled={testing || !url.trim()}
                className="inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-md bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 disabled:opacity-50 shrink-0"
              >
                {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FlaskConical className="w-3.5 h-3.5" />}
                Test URL
              </button>
            </div>
          </div>

          {testResult && (
            <div className="p-3 rounded-xl bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-xs space-y-1.5">
              <div className="flex items-center gap-1.5 font-bold text-emerald-800 dark:text-emerald-300">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{testResult.platform.toUpperCase()} Board Reachable — {testResult.sample_count} matching leads</span>
              </div>
              {testResult.sample_titles.length > 0 && (
                <ul className="list-disc pl-5 text-emerald-700 dark:text-emerald-400 space-y-0.5">
                  {testResult.sample_titles.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {testError && (
            <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 text-xs text-rose-700 dark:text-rose-300">
              {testError}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Source Name</label>
            <input 
              type="text" 
              required
              placeholder="e.g. NVIDIA Careers"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Type</label>
              <select 
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100"
              >
                <option value="ATS">Direct ATS (Zero-RAM)</option>
                <option value="WEB">Web Scraper</option>
                <option value="TELEGRAM">Telegram</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Tier</label>
              <select 
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-md p-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100"
              >
                <option value="TIER_1_TRUSTED">Tier 1 (Trusted)</option>
                <option value="TIER_2_GENERIC">Tier 2 (Generic)</option>
              </select>
            </div>
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full mt-2 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-xl transition-colors disabled:opacity-50 text-sm"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Save Source
          </button>
        </form>

        {/* Saved ATS Boards */}
        {atsSources.length > 0 && (
          <div className="mt-6 pt-5 border-t border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between gap-2 mb-3">
              <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200">Saved Direct ATS Boards ({atsSources.length})</h3>
              <button
                type="button"
                onClick={handleSyncAts}
                disabled={syncingAts}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-50"
              >
                {syncingAts ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                Sync ATS Now
              </button>
            </div>
            <div className="space-y-2 max-h-44 overflow-y-auto">
              {atsSources.map((src) => {
                const badge = detectAtsBadge(src.url_or_identifier) || "ATS";
                return (
                  <div key={src.id} className="flex items-center justify-between gap-2 p-2.5 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-200/70 dark:border-slate-700/60 text-xs">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900 dark:text-slate-100 truncate">{src.name}</span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 shrink-0">
                          {badge}
                        </span>
                      </div>
                      <p className="text-slate-500 dark:text-slate-400 truncate text-[11px] mt-0.5">{src.url_or_identifier}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDeleteSource(src.id)}
                      className="p-1.5 text-slate-400 hover:text-rose-500 rounded-lg transition-colors shrink-0"
                      title="Delete source"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
