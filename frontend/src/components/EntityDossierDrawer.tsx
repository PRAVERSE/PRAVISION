import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldCheck, 
  ExternalLink, 
  Share2, 
  MapPin, 
  Layers, 
  Tag, 
  Clock, 
  FileText, 
  Copy, 
  Check, 
  GitMerge, 
  Info 
} from 'lucide-react';
import { osintApi } from '../services/api';

interface EntityDossierDrawerProps {
  entityId: string | null;
  onClose: () => void;
  onFocusInGraph?: (entityVal: string) => void;
}

export const EntityDossierDrawer: React.FC<EntityDossierDrawerProps> = ({
  entityId,
  onClose,
  onFocusInGraph
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [dossier, setDossier] = useState<any | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  useEffect(() => {
    if (!entityId) {
      setDossier(null);
      return;
    }
    const fetchDossier = async () => {
      setLoading(true);
      try {
        const res = await osintApi.getEntityDossier(entityId);
        setDossier(res);
      } catch (err) {
        console.warn('Failed to load entity dossier:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDossier();
  }, [entityId]);

  if (!entityId) return null;

  const handleCopy = (val: string, keyName: string) => {
    navigator.clipboard.writeText(val);
    setCopiedKey(keyName);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const ent = dossier?.entity;

  return (
    <div className="fixed inset-y-0 right-0 w-96 md:w-[480px] bg-[#0A101D] border-l border-[#1E293B] shadow-2xl z-50 flex flex-col text-slate-200 transition-all duration-300">
      {/* Drawer Header */}
      <div className="p-4 border-b border-[#1E293B] flex items-center justify-between bg-[#0F172A]">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="w-5 h-5 text-sky-400" />
          <h2 className="text-sm font-bold text-white tracking-wide">ENTITY INTELLIGENCE DOSSIER</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-[#1E293B] rounded text-slate-400 hover:text-white transition cursor-pointer"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex flex-col items-center justify-center space-y-2">
          <div className="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs text-slate-400 font-mono">RETRIEVING DOSSIER TOPOLOGY...</p>
        </div>
      ) : ent ? (
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Identity Header Card */}
          <div className="p-4 bg-[#111A2E] border border-[#1E293B] rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800/40">
                {ent.entity_type}
              </span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                ent.verification_status === 'corroborated' 
                  ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40'
                  : 'bg-slate-800 text-slate-300 border border-slate-700'
              }`}>
                {ent.verification_status || 'unverified'}
              </span>
            </div>

            <h3 className="text-base font-bold text-white break-all mb-1">{ent.entity_value}</h3>
            {ent.case_number && (
              <p className="text-xs text-slate-400 font-mono">Case: {ent.case_number}</p>
            )}

            <div className="mt-3 flex items-center space-x-2">
              {onFocusInGraph && (
                <button
                  onClick={() => onFocusInGraph(ent.entity_value)}
                  className="flex items-center space-x-1.5 px-2.5 py-1 bg-sky-900/50 hover:bg-sky-800 border border-sky-700 text-sky-200 rounded text-xs transition cursor-pointer"
                >
                  <Share2 className="w-3.5 h-3.5" />
                  <span>Focus in Graph</span>
                </button>
              )}
              <button
                onClick={() => handleCopy(ent.entity_value, 'main')}
                className="flex items-center space-x-1.5 px-2.5 py-1 bg-[#1E293B] hover:bg-slate-700 text-slate-300 rounded text-xs transition cursor-pointer"
              >
                {copiedKey === 'main' ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey === 'main' ? 'Copied' : 'Copy Value'}</span>
              </button>
            </div>
          </div>

          {/* Known Aliases & Merged Identities */}
          {ent.aliases && ent.aliases.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
                <Tag className="w-3.5 h-3.5 text-indigo-400" />
                <span>KNOWN ALIASES & IDENTITY VARIATIONS ({ent.aliases.length})</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {ent.aliases.map((alias: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 bg-[#141E34] border border-[#233555] rounded text-xs text-indigo-200 font-mono"
                  >
                    {alias}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Structured Identifiers */}
          {ent.identifiers && Object.keys(ent.identifiers).length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
                <Info className="w-3.5 h-3.5 text-sky-400" />
                <span>STRUCTURED IDENTIFIERS</span>
              </div>
              <div className="grid grid-cols-1 gap-1.5">
                {Object.entries(ent.identifiers).map(([k, v]) => (
                  <div key={k} className="p-2 bg-[#0E1626] border border-[#1E293B] rounded flex justify-between items-center text-xs">
                    <span className="text-slate-400 uppercase font-mono text-[10px]">{k}</span>
                    <span className="text-white font-mono">{String(v)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Provenance Sources */}
          {ent.sources && ent.sources.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-300">
                <Layers className="w-3.5 h-3.5 text-emerald-400" />
                <span>PROVENANCE SOURCES ({ent.sources.length})</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {ent.sources.map((src: string, idx: number) => (
                  <span
                    key={idx}
                    className="px-2 py-0.5 bg-emerald-950/40 border border-emerald-800/40 rounded text-xs text-emerald-300 font-mono"
                  >
                    {src}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Connected Relationships */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
              <div className="flex items-center space-x-1.5">
                <Share2 className="w-3.5 h-3.5 text-purple-400" />
                <span>CONNECTED RELATIONSHIPS ({dossier?.relationships_count || 0})</span>
              </div>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {(dossier?.relationships || []).map((rel: any) => (
                <div key={rel.id} className="p-2 bg-[#0E1626] border border-[#1E293B] rounded text-xs flex items-center justify-between">
                  <span className="text-purple-300 font-mono text-[11px] font-medium">{rel.relationship_type}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-slate-800 text-slate-400">
                    {rel.confidence}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Linked Evidence Vault Files */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs font-semibold text-slate-300">
              <div className="flex items-center space-x-1.5">
                <FileText className="w-3.5 h-3.5 text-amber-400" />
                <span>LINKED EVIDENCE FILES ({dossier?.evidences_count || 0})</span>
              </div>
            </div>
            <div className="space-y-1.5 max-h-48 overflow-y-auto">
              {(dossier?.evidences || []).map((ev: any) => (
                <div key={ev.id} className="p-2 bg-[#0E1626] border border-[#1E293B] rounded text-xs flex items-center justify-between">
                  <div>
                    <span className="text-white block font-medium">{ev.connector_name}</span>
                    <span className="text-slate-500 font-mono text-[10px]">SHA-256: {ev.file_hash ? ev.file_hash.substring(0, 16) + '...' : 'N/A'}</span>
                  </div>
                  <span className="text-[10px] px-1.5 py-0.2 rounded font-mono bg-amber-950 text-amber-400 border border-amber-800/40">
                    {ev.file_mime_type}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          <Info className="w-8 h-8 text-slate-600 mb-2" />
          <p className="text-xs text-slate-400">No dossier found for entity ID '{entityId}'.</p>
        </div>
      )}
    </div>
  );
};

