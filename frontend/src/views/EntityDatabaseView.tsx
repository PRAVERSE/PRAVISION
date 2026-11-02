import React, { useState } from 'react';
import { 
  Database, 
  Search, 
  Filter, 
  Copy, 
  Check, 
  ShieldCheck, 
  ExternalLink,
  Tag
} from 'lucide-react';
import { EvidenceFinding, EntityType } from '../types/osint';

interface EntityDatabaseViewProps {
  findings: EvidenceFinding[];
}

export const EntityDatabaseView: React.FC<EntityDatabaseViewProps> = ({ findings }) => {
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [confidenceFilter, setConfidenceFilter] = useState<string>('all');
  const [copiedVal, setCopiedVal] = useState<string | null>(null);

  // Group unique entities
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
                          {item.value}
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
                        <td className="p-3 text-right">
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
      </div>
    </div>
  );
};

