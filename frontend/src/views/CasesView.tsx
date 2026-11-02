import React, { useState, useEffect } from 'react';
import { 
  FolderLock, 
  Plus, 
  Search, 
  Trash2, 
  Save, 
  ShieldAlert, 
  Tag, 
  Calendar, 
  User, 
  CheckCircle2, 
  AlertCircle,
  FileText
} from 'lucide-react';
import { osintApi } from '../services/api';
import { CaseDossier, ActiveInvestigation } from '../types/osint';

interface CasesViewProps {
  activeInvestigation: ActiveInvestigation | null;
  onSelectInvestigation?: (id: string) => void;
}

export const CasesView: React.FC<CasesViewProps> = ({ activeInvestigation }) => {
  const [cases, setCases] = useState<CaseDossier[]>([]);
  const [selectedCase, setSelectedCase] = useState<CaseDossier | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  
  // Create Modal state
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [title, setTitle] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [classification, setClassification] = useState<string>('RESTRICTED');
  const [tagInput, setTagInput] = useState<string>('');
  const [tags, setTags] = useState<string[]>([]);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState<string | null>(null);

  const fetchCases = async () => {
    try {
      setLoading(true);
      const data = await osintApi.listCases();
      setCases(data);
      if (data.length > 0 && !selectedCase) {
        const fullCase = await osintApi.getCase(data[0].id);
        setSelectedCase(fullCase);
      }
    } catch (err) {
      console.error('Failed to load cases:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleSelectCase = async (c: CaseDossier) => {
    try {
      const full = await osintApi.getCase(c.id);
      setSelectedCase(full);
      setSaveSuccessMsg(null);
    } catch (err) {
      console.error('Failed to fetch case detail:', err);
    }
  };

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      const newCase = await osintApi.createCase({
        title,
        description,
        classification,
        tags
      });
      setIsCreating(false);
      setTitle('');
      setDescription('');
      setTags([]);
      await fetchCases();
      setSelectedCase(newCase);
    } catch (err) {
      console.error('Failed to create case:', err);
    }
  };

  const handleDeleteCase = async (id: string) => {
    if (!confirm('Are you sure you want to delete this case dossier?')) return;
    try {
      await osintApi.deleteCase(id);
      setSelectedCase(null);
      await fetchCases();
    } catch (err) {
      console.error('Failed to delete case:', err);
    }
  };

  const handleSaveActiveToCase = async () => {
    if (!selectedCase || !activeInvestigation) return;
    try {
      await osintApi.saveActiveToCase(selectedCase.id);
      setSaveSuccessMsg('Active investigation and evidence persisted into Case dossier.');
      const updated = await osintApi.getCase(selectedCase.id);
      setSelectedCase(updated);
    } catch (err: any) {
      alert(`Error saving to case: ${err.message}`);
    }
  };

  const filteredCases = cases.filter(c => 
    c.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.case_number.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex h-full bg-[#080D1A] text-slate-200">
      {/* Sidebar Case List */}
      <div className="w-80 border-r border-[#1E293B] flex flex-col bg-[#0B132B]/50 shrink-0">
        <div className="p-4 border-b border-[#1E293B] flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <FolderLock className="w-5 h-5 text-sky-400" />
            <h2 className="font-semibold text-sm tracking-wide text-white">CASE DOSSIERS</h2>
          </div>
          <button
            onClick={() => setIsCreating(true)}
            className="p-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-md transition cursor-pointer"
            title="Create New Case"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Search */}
        <div className="p-3 border-b border-[#1E293B]">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-2.5 top-2.5" />
            <input
              type="text"
              placeholder="Search cases..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#101B33] border border-[#1E293B] rounded-md pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>

        {/* Cases List */}
        <div className="flex-1 overflow-y-auto divide-y divide-[#1E293B]">
          {loading ? (
            <div className="p-4 text-center text-xs text-slate-500">Loading case records...</div>
          ) : filteredCases.length === 0 ? (
            <div className="p-6 text-center text-xs text-slate-500">No cases found. Create a case to persist investigations.</div>
          ) : (
            filteredCases.map(c => {
              const isSelected = selectedCase?.id === c.id;
              return (
                <div
                  key={c.id}
                  onClick={() => handleSelectCase(c)}
                  className={`p-3.5 cursor-pointer transition select-none ${
                    isSelected ? 'bg-sky-950/40 border-l-2 border-sky-400' : 'hover:bg-[#101B33]/60'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-[11px] text-sky-400 font-bold">{c.case_number}</span>
                    <span className={`text-[9px] px-1.5 py-0.2 rounded font-semibold ${
                      c.classification === 'SECRET' ? 'bg-red-950/80 text-red-300 border border-red-800/40' :
                      c.classification === 'CONFIDENTIAL' ? 'bg-amber-950/80 text-amber-300 border border-amber-800/40' :
                      'bg-slate-800 text-slate-300 border border-slate-700'
                    }`}>
                      {c.classification}
                    </span>
                  </div>
                  <h3 className="text-xs font-medium text-slate-200 truncate mb-1">{c.title}</h3>
                  <div className="flex items-center text-[10px] text-slate-500 space-x-3">
                    <span>{new Date(c.created_at).toLocaleDateString()}</span>
                    <span>•</span>
                    <span className="capitalize">{c.status}</span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Main Case Workspace */}
      <div className="flex-1 flex flex-col overflow-y-auto">
        {selectedCase ? (
          <div className="p-6 space-y-6 max-w-5xl">
            {/* Header / Actions */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center space-x-3 mb-2">
                    <span className="font-mono text-sm text-sky-400 font-bold">{selectedCase.case_number}</span>
                    <span className="px-2 py-0.5 rounded text-xs font-semibold bg-sky-900/40 text-sky-300 border border-sky-700/50">
                      {selectedCase.classification}
                    </span>
                    <span className="px-2 py-0.5 rounded text-xs font-semibold bg-emerald-950/40 text-emerald-300 border border-emerald-800/40 uppercase">
                      {selectedCase.status}
                    </span>
                  </div>
                  <h1 className="text-xl font-bold text-white mb-1">{selectedCase.title}</h1>
                  <p className="text-xs text-slate-400 leading-relaxed">{selectedCase.description || 'No case description provided.'}</p>
                </div>

                <div className="flex items-center space-x-2">
                  {activeInvestigation && (
                    <button
                      onClick={handleSaveActiveToCase}
                      className="flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-medium transition cursor-pointer"
                    >
                      <Save className="w-3.5 h-3.5" />
                      <span>Save Active Inv</span>
                    </button>
                  )}
                  <button
                    onClick={() => handleDeleteCase(selectedCase.id)}
                    className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-red-950/30 rounded transition cursor-pointer"
                    title="Delete Case"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {saveSuccessMsg && (
                <div className="mt-4 p-2.5 bg-emerald-950/40 border border-emerald-800/40 rounded text-xs text-emerald-300 flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{saveSuccessMsg}</span>
                </div>
              )}

              {/* Case Metadata Bar */}
              <div className="grid grid-cols-4 gap-4 mt-5 pt-4 border-t border-[#1E293B] text-xs">
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Assigned Analyst</span>
                  <span className="text-slate-300 font-medium flex items-center space-x-1 mt-0.5">
                    <User className="w-3 h-3 text-slate-400" />
                    <span>{selectedCase.created_by}</span>
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Created On</span>
                  <span className="text-slate-300 font-medium flex items-center space-x-1 mt-0.5">
                    <Calendar className="w-3 h-3 text-slate-400" />
                    <span>{new Date(selectedCase.created_at).toLocaleString()}</span>
                  </span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Linked Entities</span>
                  <span className="text-slate-300 font-bold text-sm mt-0.5">{selectedCase.entities_count || 0}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-mono">Evidence Vault Items</span>
                  <span className="text-slate-300 font-bold text-sm mt-0.5">{selectedCase.evidence_count || 0}</span>
                </div>
              </div>

              {/* Tags */}
              {selectedCase.tags && selectedCase.tags.length > 0 && (
                <div className="flex items-center space-x-2 mt-4 pt-3 border-t border-[#1E293B]">
                  <Tag className="w-3 h-3 text-slate-500" />
                  <div className="flex flex-wrap gap-1.5">
                    {selectedCase.tags.map((t, idx) => (
                      <span key={idx} className="text-[10px] px-2 py-0.5 bg-slate-800 text-slate-300 rounded font-mono">
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Linked Investigations */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-5">
              <h2 className="text-sm font-semibold text-white mb-3 flex items-center space-x-2">
                <FileText className="w-4 h-4 text-sky-400" />
                <span>SAVED INVESTIGATIONS ({selectedCase.investigations?.length || 0})</span>
              </h2>

              {(!selectedCase.investigations || selectedCase.investigations.length === 0) ? (
                <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-[#1E293B] rounded-lg">
                  No investigations saved in this case yet. Run an investigation and click &quot;Save Active Inv&quot; above.
                </div>
              ) : (
                <div className="space-y-3">
                  {selectedCase.investigations.map((inv: any) => (
                    <div key={inv.id} className="p-3 bg-[#131F37] border border-[#1E293B] rounded-md flex items-center justify-between">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-semibold text-white">{inv.root_input}</span>
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-950 text-sky-400 border border-sky-800/40">
                            {inv.root_type}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">({inv.mode})</span>
                        </div>
                        <div className="text-[11px] text-slate-400 mt-1">
                          Findings: <span className="font-semibold text-slate-200">{inv.total_findings}</span> | Relational Links: <span className="font-semibold text-slate-200">{inv.verified_relationships}</span>
                        </div>
                      </div>
                      <span className="text-[10px] text-slate-500 font-mono">
                        {inv.completed_at ? new Date(inv.completed_at).toLocaleDateString() : ''}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
            <FolderLock className="w-12 h-12 text-slate-700 mb-3" />
            <h3 className="text-base font-semibold text-slate-300">No Case Selected</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">Select an existing case dossier from the left sidebar or create a new case to organize investigation findings.</p>
          </div>
        )}
      </div>

      {/* Create Case Modal */}
      {isCreating && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg w-full max-w-md p-6 shadow-2xl">
            <h2 className="text-base font-bold text-white mb-4 flex items-center space-x-2">
              <FolderLock className="w-5 h-5 text-sky-400" />
              <span>Create Intelligence Case</span>
            </h2>

            <form onSubmit={handleCreateCase} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1 font-medium">Case Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Operation Obsidian Sentinel"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded p-2 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Description</label>
                <textarea
                  rows={3}
                  placeholder="Operational scope, objectives, target profiles..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded p-2 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Classification Level</label>
                <select
                  value={classification}
                  onChange={(e) => setClassification(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded p-2 text-white focus:outline-none focus:border-sky-500"
                >
                  <option value="UNCLASSIFIED">UNCLASSIFIED</option>
                  <option value="RESTRICTED">RESTRICTED</option>
                  <option value="CONFIDENTIAL">CONFIDENTIAL</option>
                  <option value="SECRET">SECRET</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Tags (Press Enter to add)</label>
                <input
                  type="text"
                  placeholder="e.g. adversary, malware, fraud"
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      if (tagInput.trim() && !tags.includes(tagInput.trim())) {
                        setTags([...tags, tagInput.trim()]);
                        setTagInput('');
                      }
                    }
                  }}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded p-2 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
                {tags.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-2">
                    {tags.map((t, idx) => (
                      <span key={idx} className="bg-slate-800 text-slate-300 text-[10px] px-2 py-0.5 rounded flex items-center space-x-1">
                        <span>#{t}</span>
                        <button type="button" onClick={() => setTags(tags.filter((_, i) => i !== idx))} className="text-slate-400 hover:text-red-400">×</button>
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="flex items-center justify-end space-x-2 pt-3 border-t border-[#1E293B]">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded transition cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded font-medium transition cursor-pointer"
                >
                  Create Dossier
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

