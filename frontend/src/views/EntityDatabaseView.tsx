import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Copy, 
  Check, 
  ShieldCheck, 
  ExternalLink,
  Tag,
  GitMerge,
  AlertTriangle,
  Eye,
  CheckCircle2,
  RefreshCw
} from 'lucide-react';
import { EvidenceFinding, EntityType, CaseDossier } from '../types/osint';
import { osintApi } from '../services/api';

interface EntityDatabaseViewProps {
  findings: EvidenceFinding[];
  onSelectEntity?: (entityVal: string) => void;
}

export const EntityDatabaseView: React.FC<EntityDatabaseViewProps> = ({ 
  findings,
  onSelectEntity 
}) => {
  const [activeTab, setActiveTab] = useState<'directory' | 'merge_candidates'>('directory');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [confidenceFilter, setConfidenceFilter] = useState<string>('all');
  const [copiedVal, setCopiedVal] = useState<string | null>(null);

  // Merge candidate state
  const [cases, setCases] = useState<CaseDossier[]>([]);
  const [selectedCaseId, setSelectedCaseId] = useState<string>('');
  const [candidates, setCandidates] = useState<any[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [mergeStatusMsg, setMergeStatusMsg] = useState<string | null>(null);

  // Group unique entities from in-memory findings
  const entityMap = new Map<string, {
    value: string;
    type: EntityType;
    confidence: string;
    sources: Set<string>;
    firstSeen: string;
    lastFinding: EvidenceFinding;
  }>();

  findings.forEach(f => {
    const key = `${f.entity_type}:${f.entity_value.toLowerCase().trim()}`;
    if (!entityMap.has(key)) {
      entityMap.set(key, {
        value: f.entity_value,
        type: f.entity_type,
        confidence: f.confidence,
        sources: new Set([f.source_name]),
        firstSeen: f.collection_timestamp,
        lastFinding: f
      });
    } else {
      const existing = entityMap.get(key)!;
      existing.sources.add(f.source_name);
      if (f.confidence === 'independently_corroborated' || f.confidence === 'high') {
        existing.confidence = f.confidence;
      }
    }
  });

  const uniqueEntities = Array.from(entityMap.values());

  const filtered = uniqueEntities.filter(e => {
    if (typeFilter !== 'all' && e.type !== typeFilter) return false;
    if (confidenceFilter !== 'all' && e.confidence !== confidenceFilter) return false;
    if (searchQuery && !e.value.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    return true;
  });

  const handleCopy = (val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedVal(val);
    setTimeout(() => setCopiedVal(null), 2000);
  };

  // Load cases on mount for candidate resolution
  useEffect(() => {
    const loadCases = async () => {
      try {
        const caseList = await osintApi.listCases();
        setCases(caseList);
        if (caseList.length > 0 && !selectedCaseId) {
          setSelectedCaseId(caseList[0].id);
        }
      } catch (err) {
        console.warn('Error loading cases for entity DB:', err);
      }
    };
    loadCases();
  }, []);

  const fetchCandidates = async (caseId: string) => {
    if (!caseId) return;
    setLoadingCandidates(true);
    setMergeStatusMsg(null);
    try {
      const res = await osintApi.getCaseMergeCandidates(caseId);
      setCandidates(res);
    } catch (err) {
      console.warn('Error fetching candidates:', err);
    } finally {
      setLoadingCandidates(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'merge_candidates' && selectedCaseId) {
      fetchCandidates(selectedCaseId);
    }
  }, [activeTab, selectedCaseId]);

  const handleExecuteMerge = async (canonicalId: string, absorbedId: string, reason: string) => {
    try {
      await osintApi.mergeEntities(canonicalId, [absorbedId], reason);
      setMergeStatusMsg(`Successfully merged entity ${absorbedId} into canonical identity.`);
      fetchCandidates(selectedCaseId);
    } catch (err: any) {
      alert(`Merge failed: ${err.message || err}`);
    }
  };

  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center space-x-2">
              <Database className="w-5 h-5 text-sky-400" />
              <h1 className="text-lg font-bold text-white tracking-wide">STRUCTURED ENTITY DATABASE</h1>
            </div>
            <p className="text-xs text-slate-400 mt-1">Cross-source deduplicated entity directory, provenance corroborated sources, and confidence scoring.</p>
          </div>

          <div className="flex items-center space-x-3 text-xs font-mono">
            <div className="bg-[#0F172A] px-3 py-1.5 rounded border border-[#1E293B]">
              <span className="text-slate-500 block text-[10px]">TOTAL ENTITIES</span>
              <span className="text-sky-400 font-bold">{uniqueEntities.length}</span>
            </div>
          </div>
        </div>

        {/* Tab Switcher */}
        <div className="flex border-b border-[#1E293B] space-x-4 text-xs font-medium">
          <button
            onClick={() => setActiveTab('directory')}
            className={`pb-2.5 flex items-center space-x-2 cursor-pointer transition ${
              activeTab === 'directory'
                ? 'text-sky-400 border-b-2 border-sky-400 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <Database className="w-4 h-4" />
            <span>ENTITY DIRECTORY ({uniqueEntities.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('merge_candidates')}
            className={`pb-2.5 flex items-center space-x-2 cursor-pointer transition ${
              activeTab === 'merge_candidates'
                ? 'text-purple-400 border-b-2 border-purple-400 font-bold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <GitMerge className="w-4 h-4" />
            <span>IDENTITY MERGE REVIEW {candidates.length > 0 && `(${candidates.length})`}</span>
          </button>
        </div>

        {activeTab === 'directory' && (
          <>
            {/* Filter Controls */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-3.5 flex flex-wrap items-center justify-between gap-3 text-xs">
              <div className="flex items-center space-x-2 flex-1 min-w-[200px]">
                <Search className="w-4 h-4 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search entity registry..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded px-3 py-1.5 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 text-xs"
                />
              </div>

              <div className="flex items-center space-x-2">
                <Filter className="w-3.5 h-3.5 text-slate-400" />
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="bg-[#131F37] border border-[#1E293B] rounded px-2.5 py-1.5 text-white text-xs focus:outline-none"
                >
                  <option value="all">All Entity Types</option>
                  {Array.from(new Set(uniqueEntities.map(e => e.type))).map(t => (
                    <option key={t} value={t}>{t.toUpperCase()}</option>
                  ))}
                </select>

                <select
                  value={confidenceFilter}
                  onChange={(e) => setConfidenceFilter(e.target.value)}
                  className="bg-[#131F37] border border-[#1E293B] rounded px-2.5 py-1.5 text-white text-xs focus:outline-none"
                >
                  <option value="all">All Confidence Levels</option>
                  <option value="independently_corroborated">Corroborated</option>
                  <option value="high">High</option>
                  <option value="moderate">Moderate</option>
                  <option value="low">Low</option>
                  <option value="unverified">Unverified</option>
                </select>
              </div>
            </div>

            {/* Entities Table */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg overflow-hidden">
              {filtered.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-500">
                  No matching entities found in current directory.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-[#131F37] border-b border-[#1E293B] text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                        <th className="p-3">Entity Value</th>
                        <th className="p-3">Type</th>
                        <th className="p-3">Corroborating Sources</th>
                        <th className="p-3">Confidence</th>
                        <th className="p-3">First Seen</th>
                        <th className="p-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#1E293B]">
                      {filtered.map((item, idx) => {
                        const sourcesArr = Array.from(item.sources);
                        return (
                          <tr key={idx} className="hover:bg-[#101B33]/60 transition">
                            <td className="p-3 font-semibold text-white break-all max-w-xs font-mono">
                              <span 
                                onClick={() => onSelectEntity && onSelectEntity(item.value)}
                                className="cursor-pointer hover:text-sky-400"
                              >
                                {item.value}
                              </span>
                            </td>
                            <td className="p-3">
                              <span className="text-[10px] px-1.5 py-0.5 rounded font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                                {item.type}
                              </span>
                            </td>
                            <td className="p-3">
                              <div className="flex flex-wrap gap-1">
                                {sourcesArr.map((s, sIdx) => (
                                  <span key={sIdx} className="text-[10px] px-1.5 py-0.2 rounded bg-sky-950 text-sky-400 border border-sky-800/40 font-mono">
                                    {s}
                                  </span>
                                ))}
                              </div>
                            </td>
                            <td className="p-3">
                              <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                                item.confidence === 'high' || item.confidence === 'independently_corroborated'
                                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                                  : 'bg-amber-950 text-amber-400 border border-amber-800/40'
                              }`}>
                                {item.confidence}
                              </span>
                            </td>
                            <td className="p-3 text-[10px] text-slate-500 font-mono">
                              {new Date(item.firstSeen).toLocaleDateString()}
                            </td>
                            <td className="p-3 text-right space-x-1">
                              {onSelectEntity && (
                                <button
                                  onClick={() => onSelectEntity(item.value)}
                                  className="p-1 text-slate-400 hover:text-sky-300 rounded hover:bg-[#131F37] transition cursor-pointer"
                                  title="Inspect Entity Dossier"
                                >
                                  <Eye className="w-3.5 h-3.5" />
                                </button>
                              )}
                              <button
                                onClick={() => handleCopy(item.value)}
                                className="p-1 text-slate-400 hover:text-white rounded hover:bg-[#131F37] transition cursor-pointer"
                                title="Copy Entity Value"
                              >
                                {copiedVal === item.value ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === 'merge_candidates' && (
          <div className="space-y-4">
            {/* Case Selector */}
            <div className="flex items-center justify-between bg-[#0F172A] border border-[#1E293B] p-3 rounded-lg text-xs">
              <div className="flex items-center space-x-2">
                <span className="text-slate-400">Select Case Scope:</span>
                <select
                  value={selectedCaseId}
                  onChange={(e) => setSelectedCaseId(e.target.value)}
                  className="bg-[#131F37] border border-[#1E293B] rounded px-3 py-1.5 text-white font-mono focus:outline-none"
                >
                  {cases.map(c => (
                    <option key={c.id} value={c.id}>{c.case_number}: {c.title}</option>
                  ))}
                </select>
              </div>

              <button
                onClick={() => fetchCandidates(selectedCaseId)}
                disabled={loadingCandidates}
                className="flex items-center space-x-1 px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loadingCandidates ? 'animate-spin' : ''}`} />
                <span>Re-evaluate Candidates</span>
              </button>
            </div>

            {mergeStatusMsg && (
              <div className="p-3 bg-emerald-950/40 border border-emerald-800/40 rounded-lg text-xs text-emerald-300 flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                <span>{mergeStatusMsg}</span>
              </div>
            )}

            {loadingCandidates ? (
              <div className="p-12 text-center text-xs text-slate-400">
                Evaluating multi-factor identity candidates...
              </div>
            ) : candidates.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-500 bg-[#0F172A] border border-[#1E293B] rounded-lg">
                No duplicate identity candidate pairs found meeting resolution threshold in this case.
              </div>
            ) : (
              <div className="space-y-3">
                {candidates.map(cand => (
                  <div key={cand.candidate_pair_id} className="p-4 bg-[#0F172A] border border-[#1E293B] rounded-lg space-y-3 text-xs">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <span className="px-2 py-0.5 rounded font-mono text-[10px] bg-purple-950 text-purple-300 border border-purple-800/40">
                          {cand.match_type}
                        </span>
                        <span className="font-mono text-slate-400">
                          Match Score: <strong className="text-sky-400">{Math.round(cand.match_score * 100)}%</strong>
                        </span>
                      </div>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono ${
                        cand.recommendation === 'auto_merge' 
                          ? 'bg-emerald-950 text-emerald-300' 
                          : 'bg-amber-950 text-amber-300'
                      }`}>
                        {cand.recommendation.toUpperCase()}
                      </span>
                    </div>

                    {/* Entities Pair Comparison */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 bg-[#080D1A] p-3 rounded border border-[#182338]">
                      <div>
                        <span className="text-slate-500 font-mono text-[10px] block uppercase">Canonical Candidate (Entity A)</span>
                        <h4 className="text-white font-mono font-semibold break-all">{cand.entity_a.value}</h4>
                        <span className="text-[10px] text-slate-400 font-mono">Type: {cand.entity_a.type} | Conf: {cand.entity_a.confidence}</span>
                      </div>

                      <div>
                        <span className="text-slate-500 font-mono text-[10px] block uppercase">Candidate to Absorb (Entity B)</span>
                        <h4 className="text-white font-mono font-semibold break-all">{cand.entity_b.value}</h4>
                        <span className="text-[10px] text-slate-400 font-mono">Type: {cand.entity_b.type} | Conf: {cand.entity_b.confidence}</span>
                      </div>
                    </div>

                    {/* Explainable Factor Breakdown */}
                    {cand.explainable_factors && cand.explainable_factors.length > 0 && (
                      <div className="space-y-1">
                        <span className="text-[10px] uppercase font-mono text-slate-400 block font-semibold">Explainable Factors:</span>
                        <div className="flex flex-wrap gap-1.5">
                          {cand.explainable_factors.map((f: any, idx: number) => (
                            <span key={idx} className="p-1.5 bg-[#131F37] border border-[#233555] rounded text-[10px] text-slate-300">
                              <strong className="text-sky-300">{f.factor}:</strong> {f.description} (Weight: {f.weight})
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Conflicts */}
                    {cand.conflicts && cand.conflicts.length > 0 && (
                      <div className="p-2 bg-red-950/40 border border-red-800/40 rounded text-red-300 text-[11px] flex items-center space-x-2">
                        <AlertTriangle className="w-4 h-4 shrink-0 text-red-400" />
                        <span>{cand.conflicts.join('; ')}</span>
                      </div>
                    )}

                    {/* Action Button */}
                    <div className="pt-2 flex justify-end">
                      <button
                        onClick={() => handleExecuteMerge(cand.entity_a.id, cand.entity_b.id, `Confirmed match (${Math.round(cand.match_score * 100)}%)`)}
                        className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded font-medium text-xs flex items-center space-x-1.5 cursor-pointer transition"
                      >
                        <GitMerge className="w-3.5 h-3.5" />
                        <span>Review & Merge Entities</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default EntityDatabaseView;
