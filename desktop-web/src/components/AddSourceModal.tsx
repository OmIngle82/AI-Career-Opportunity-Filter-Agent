import { useState } from "react";
import { API_BASE_URL } from "@/lib/api";
import { X, Plus, Loader2 } from "lucide-react";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function AddSourceModal({ isOpen, onClose, onSuccess }: Props) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [type, setType] = useState("WEB");
  const [tier, setTier] = useState("TIER_2_GENERIC");
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE_URL}/sources`, {
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
        onSuccess();
        onClose();
      } else {
        console.error("Failed to add source");
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-100 dark:border-slate-800 w-full max-w-md p-6 relative">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 mb-6">Add New Source</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Source Name</label>
            <input 
              type="text" 
              required
              placeholder="e.g. Indeed India"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">URL or Identifier</label>
            <input 
              type="text" 
              required
              placeholder="https://..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100 placeholder-slate-400 dark:placeholder-slate-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Type</label>
              <select 
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100"
              >
                <option value="WEB">Web Scraper</option>
                <option value="TELEGRAM">Telegram</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">Tier</label>
              <select 
                value={tier}
                onChange={(e) => setTier(e.target.value)}
                className="w-full bg-transparent border border-slate-200 dark:border-slate-700 rounded-md p-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-shadow text-slate-900 dark:text-slate-100"
              >
                <option value="TIER_1_TRUSTED">Tier 1 (Trusted)</option>
                <option value="TIER_2_GENERIC">Tier 2 (Generic)</option>
              </select>
            </div>
          </div>

          <button 
            type="submit" 
            disabled={loading}
            className="w-full mt-4 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 rounded-xl transition-colors disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
            Save Source
          </button>
        </form>
      </div>
    </div>
  );
}
