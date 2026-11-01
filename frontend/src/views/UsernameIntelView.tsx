import React, { useState } from 'react';
import { User, ArrowRight, ExternalLink, Globe } from 'lucide-react';
import { EvidenceFinding } from '../types/osint';

interface UsernameIntelViewProps {
  onStartInvestigation: (target: string, mode: string, depth?: number) => void;
  findings: EvidenceFinding[];
}

export const UsernameIntelView: React.FC<UsernameIntelViewProps> = ({ onStartInvestigation, findings }) => {
  const [username, setUsername] = useState('');

  const usernameFindings = findings.filter(f => f.entity_type === 'username' || f.entity_type === 'url');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (username.trim()) {
      onStartInvestigation(username.trim().replace(/^@/, ''), 'mode_1_identity', 2);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="border-b border-[#26364B] pb-4">
        <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Mode 1: Public Identity & Username Intelligence</h1>
        <p className="text-xs text-[#94A3B8]">
          Cross-platform profile discovery across Sherlock, Maigret, GHunt, and SocialScan. Collects public profiles, bio links, and verified handles.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-xl flex gap-4">
        <div className="relative flex-1">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="handle or username (e.g. torvalds)"
            className="w-full bg-[#080D16] border border-[#26364B] focus:border-sky-500 rounded-xl px-4 py-3 pl-11 text-sm text-[#F8FAFC] font-mono focus:outline-none"
          />
          <User className="w-5 h-5 text-sky-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        </div>
        <button
          type="submit"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-bold text-xs flex items-center space-x-2 cursor-pointer transition-all"
        >
          <span>Hunt User Profiles</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      {/* Discovered Profiles Grid */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold text-[#F8FAFC] uppercase tracking-wider">
          Verified Public Profiles ({usernameFindings.length})
        </h2>

        {usernameFindings.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {usernameFindings.map((f) => (
              <div key={f.id} className="p-4 rounded-xl bg-[#0E1624] border border-[#26364B] space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#F8FAFC] truncate max-w-[200px]">{f.source_name}</span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    {f.confidence}
                  </span>
                </div>
                {f.source_url ? (
                  <a 
                    href={f.source_url} 
                    target="_blank" 
                    rel="noreferrer" 
                    className="text-sky-400 hover:underline flex items-center space-x-1 truncate font-mono text-[11px]"
                  >
                    <span className="truncate">{f.source_url}</span>
                    <ExternalLink className="w-3 h-3 shrink-0" />
                  </a>
                ) : (
                  <div className="font-mono text-[#CBD5E1]">{f.entity_value}</div>
                )}
                <p className="text-[#94A3B8] text-[11px]">{f.evidence_description}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-[#64748B]">
            No username profiles identified in volatile memory. Enter a handle to query public social networks.
          </div>
        )}
      </div>
    </div>
  );
};
