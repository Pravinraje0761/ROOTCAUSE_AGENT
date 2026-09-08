import { useState, useEffect } from 'react';
import { X, FolderGit2, Link2, GitBranch, RefreshCw, Search, FileCode, Database, ShieldAlert, Info } from 'lucide-react';

interface Workspace {
  workspace_id: string;
  name: string;
  source: string;
  url: string;
  root: string;
  branch: string;
  connected_at: string | null;
  last_analyzed_at: string | null;
  metadata: any;
}

interface Finding {
  severity: string;
  title: string;
  detail: string;
  evidence: string;
  category: string;
  file?: string;
}

interface AnalysisResult {
  workspace_id: string;
  metadata: any;
  findings: Finding[];
  summary: string;
}

const SEVERITY_STYLE: Record<string, { label: string; cls: string }> = {
  high: { label: 'High', cls: 'bg-red-500/15 border-red-500/40 text-red-400' },
  medium: { label: 'Medium', cls: 'bg-amber-500/15 border-amber-500/40 text-amber-400' },
  low: { label: 'Low', cls: 'bg-yellow-500/15 border-yellow-500/40 text-yellow-300' },
  info: { label: 'Info', cls: 'bg-blue-500/15 border-blue-500/40 text-blue-400' },
};

export default function WorkspacePanel({ onClose }: { onClose: () => void }) {
  const [source, setSource] = useState<'github' | 'local'>('github');
  const [url, setUrl] = useState('');
  const [path, setPath] = useState('');
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState<Workspace | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchWorkspaces = async () => {
    try {
      const res = await fetch('/api/workspace/list');
      const data = await res.json();
      setWorkspaces(data.workspaces || []);
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchWorkspaces();
  }, []);

  const handleConnect = async () => {
    setBusy(true);
    setError(null);
    try {
      const body = source === 'github'
        ? { source, url: url.trim() }
        : { source, path: path.trim() };
      const res = await fetch('/api/workspace/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Connect failed');
        setBusy(false);
        return;
      }
      setUrl('');
      setPath('');
      await fetchWorkspaces();
      setSelected(data);
      setAnalysis(null);
    } catch (e: any) {
      setError(e.message || 'Connect failed');
    } finally {
      setBusy(false);
    }
  };

  const handleSelect = (w: Workspace) => {
    setSelected(w);
    setAnalysis(null);
  };

  const handleAnalyze = async () => {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch('/api/workspace/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: selected.workspace_id }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || 'Analysis failed');
        setBusy(false);
        return;
      }
      setAnalysis(data);
      await fetchWorkspaces();
    } catch (e: any) {
      setError(e.message || 'Analysis failed');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (w: Workspace) => {
    setBusy(true);
    setError(null);
    try {
      await fetch(`/api/workspace/${w.workspace_id}`, { method: 'DELETE' });
      if (selected?.workspace_id === w.workspace_id) {
        setSelected(null);
        setAnalysis(null);
      }
      await fetchWorkspaces();
    } catch (e: any) {
      setError(e.message || 'Delete failed');
    } finally {
      setBusy(false);
    }
  };

  const meta = selected?.metadata || analysis?.metadata || {};
  const langs = Object.entries(meta.languages || {}) as [string, number][];

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0b0f19] border border-gray-800 rounded-2xl max-w-4xl w-full flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-gray-800 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="bg-gradient-to-tr from-emerald-600 to-teal-600 p-2 rounded-lg text-white">
              <FolderGit2 size={18} />
            </div>
            <div>
              <h3 className="text-sm font-bold text-gray-100">Connect a Workspace</h3>
              <p className="text-xs text-gray-500">Attach a real repository for live codebase investigation</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-300"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Connect form */}
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={() => setSource('github')}
              className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-semibold transition ${source === 'github' ? 'bg-blue-600/20 border-blue-500/60 text-blue-300' : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'}`}
            >
              <GitBranch size={15} /> GitHub Repo
            </button>
            <button
              onClick={() => setSource('local')}
              className={`flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border text-sm font-semibold transition ${source === 'local' ? 'bg-blue-600/20 border-blue-500/60 text-blue-300' : 'bg-gray-900/40 border-gray-800 text-gray-400 hover:border-gray-700'}`}
            >
              <FolderGit2 size={15} /> Local Path
            </button>
          </div>

          <div className="flex gap-3">
            {source === 'github' ? (
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/owner/repo"
                className="flex-1 bg-gray-950/60 border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500/60"
              />
            ) : (
              <input
                value={path}
                onChange={(e) => setPath(e.target.value)}
                placeholder="C:\\path\\to\\local\\repository"
                className="flex-1 bg-gray-950/60 border border-gray-800 rounded-lg px-3 py-2.5 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500/60"
              />
            )}
            <button
              onClick={handleConnect}
              disabled={busy || (source === 'github' ? !url.trim() : !path.trim())}
              className="px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold disabled:opacity-50 transition flex items-center gap-2"
            >
              <Link2 size={15} /> Connect
            </button>
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">{error}</div>
          )}

          {/* Workspaces list */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold uppercase tracking-wider text-gray-400">Connected Workspaces</span>
              <button onClick={fetchWorkspaces} className="text-gray-500 hover:text-gray-300"><RefreshCw size={13} /></button>
            </div>
            <div className="space-y-2">
              {workspaces.length === 0 && (
                <div className="text-xs text-gray-600 border border-dashed border-gray-800 rounded-lg p-4 text-center">
                  No workspaces connected yet. Connect a GitHub URL or a local path to begin.
                </div>
              )}
              {workspaces.map((w) => (
                <div
                  key={w.workspace_id}
                  onClick={() => handleSelect(w)}
                  className={`cursor-pointer p-3 rounded-lg border text-xs flex items-center justify-between gap-2 transition ${selected?.workspace_id === w.workspace_id ? 'bg-[#0f172a] border-blue-500/50' : 'bg-gray-950/30 border-gray-800 hover:border-gray-700'}`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    {w.source === 'github' ? <GitBranch size={14} className="text-gray-400 shrink-0" /> : <FolderGit2 size={14} className="text-gray-400 shrink-0" />}
                    <div className="min-w-0">
                      <div className="font-bold text-gray-200 truncate">{w.name}</div>
                      <div className="text-[10px] text-gray-500 truncate">{w.source === 'github' ? w.url : w.root}</div>
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleDelete(w); }}
                    className="text-gray-600 hover:text-red-400 shrink-0"
                    title="Disconnect"
                  >
                    <X size={13} />
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Selected workspace metadata + analyze */}
          {selected && (
            <div className="border border-gray-800/80 rounded-xl p-4 space-y-4 bg-gray-950/30">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Search size={14} className="text-blue-400" />
                  <span className="text-xs font-bold text-gray-200">{selected.name}</span>
                  {meta.branch && (
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-800 text-gray-400 flex items-center gap-1"><GitBranch size={9} /> {meta.branch}</span>
                  )}
                </div>
                <button
                  onClick={handleAnalyze}
                  disabled={busy}
                  className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold disabled:opacity-50 transition flex items-center gap-1.5"
                >
                  {busy ? <RefreshCw size={13} className="animate-spin" /> : <Search size={13} />}
                  Investigate this repository
                </button>
              </div>

              {meta.file_count !== undefined && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  <Stat label="Files" value={meta.file_count} />
                  <Stat label="Code Files" value={meta.code_file_count} />
                  <Stat label="Commits" value={meta.total_commits} />
                  <Stat label="Manifests" value={(meta.manifests || []).length} />
                </div>
              )}

              {langs.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {langs.map(([lang, count]) => (
                    <span key={lang} className="text-[10px] px-2 py-0.5 rounded-full bg-gray-800/80 text-gray-300 flex items-center gap-1">
                      <FileCode size={9} className="text-blue-400" /> {lang} <b className="text-gray-500">{count}</b>
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Analysis results */}
          {analysis && (
            <div className="border border-emerald-500/20 rounded-xl p-4 space-y-4 bg-emerald-500/[0.03]">
              <div className="flex items-center gap-2">
                <ShieldAlert size={15} className="text-emerald-400" />
                <span className="text-sm font-bold text-gray-100">Codebase Investigation</span>
              </div>
              <p className="text-xs text-gray-400 leading-relaxed bg-[#05080e] border border-gray-800 rounded-lg p-3">{analysis.summary}</p>

              {analysis.findings.length === 0 && (
                <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-3 flex items-center gap-2">
                  <Info size={13} /> No dependency or git-history risk signals detected in this snapshot.
                </div>
              )}

              <div className="space-y-2">
                {analysis.findings.map((f, i) => {
                  const s = SEVERITY_STYLE[f.severity] || SEVERITY_STYLE.info;
                  return (
                    <div key={i} className="rounded-lg border border-gray-800 bg-gray-950/40 p-3 space-y-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
                        <span className="text-xs font-semibold text-gray-200">{f.title}</span>
                      </div>
                      <p className="text-xs text-gray-400 leading-relaxed">{f.detail}</p>
                      <div className="flex items-center gap-2 text-[10px]">
                        {f.file && (
                          <span className="text-gray-500 bg-gray-800/60 px-2 py-0.5 rounded flex items-center gap-1"><FileCode size={9} /> {f.file}</span>
                        )}
                        <span className="text-gray-600 font-mono">{f.evidence}</span>
                        <span className="text-gray-600 font-mono ml-auto">{f.category}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-gray-800 px-6 py-3 flex items-center justify-between">
          <span className="text-[10px] text-gray-600 flex items-center gap-1.5">
            <Database size={11} /> Real-codebase analysis via git history, dependency manifests, and change hotspots.
          </span>
          <button onClick={onClose} className="text-xs text-gray-400 hover:text-gray-200 font-semibold">Close</button>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-gray-950/60 border border-gray-800 rounded-lg p-2.5">
      <div className="text-sm font-bold text-gray-100">{value}</div>
      <div className="text-[10px] uppercase tracking-wider text-gray-500">{label}</div>
    </div>
  );
}
