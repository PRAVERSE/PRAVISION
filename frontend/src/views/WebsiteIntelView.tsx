import React, { useState } from 'react';
import { Globe2, ArrowRight, ShieldCheck, Server, Lock, ExternalLink } from 'lucide-react';
import { EvidenceFinding } from '../types/osint';

interface WebsiteIntelViewProps {
  onStartInvestigation: (target: string, mode: string, depth?: number) => void;
  findings: EvidenceFinding[];
}

export const WebsiteIntelView: React.FC<WebsiteIntelViewProps> = ({ onStartInvestigation, findings }) => {
  const [domain, setDomain] = useState('');

  const webFindings = findings.filter(f => 
    f.entity_type === 'domain' || 
    f.entity_type === 'subdomain' || 
    f.entity_type === 'dns_record' || 
    f.entity_type === 'technology'
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (domain.trim()) {
      onStartInvestigation(domain.trim(), 'mode_5_website_domain', 2);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="border-b border-[#26364B] pb-4">
        <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Mode 5: Website & Domain Intelligence</h1>
        <p className="text-xs text-[#94A3B8]">
          Subdomain discovery via Certificate Transparency (CRT.sh), multi-record DNS resolution (A, MX, NS, TXT), TLS certificate profiling, and WhatWeb technology fingerprinter.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-xl flex gap-4">
        <div className="relative flex-1">
          <input
            type="text"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="target-domain.com or https://site.org"
            className="w-full bg-[#080D16] border border-[#26364B] focus:border-sky-500 rounded-xl px-4 py-3 pl-11 text-sm text-[#F8FAFC] font-mono focus:outline-none"
          />
          <Globe2 className="w-5 h-5 text-sky-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        </div>
        <button
          type="submit"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-bold text-xs flex items-center space-x-2 cursor-pointer transition-all"
        >
          <span>Analyze Domain</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold text-[#F8FAFC] uppercase tracking-wider">
          DNS, Subdomains & Technology Stack ({webFindings.length})
        </h2>

        {webFindings.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {webFindings.map((f) => (
              <div key={f.id} className="p-4 rounded-xl bg-[#0E1624] border border-[#26364B] space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sky-400 font-bold truncate max-w-[200px]">{f.entity_value}</span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                    {f.entity_type}
                  </span>
                </div>
                <p className="text-[#CBD5E1] text-[11px]">{f.evidence_description}</p>
                <div className="text-[10px] text-[#64748B]">Source: {f.source_name}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-[#64748B]">
            No domain assets discovered in volatile memory. Enter a domain or hostname to map records.
          </div>
        )}
      </div>
    </div>
  );
};

