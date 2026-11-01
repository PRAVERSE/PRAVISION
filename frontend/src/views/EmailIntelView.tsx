import React, { useState } from 'react';
import { Mail, ArrowRight, ShieldCheck, CheckCircle2, AlertTriangle } from 'lucide-react';
import { EvidenceFinding } from '../types/osint';

interface EmailIntelViewProps {
  onStartInvestigation: (target: string, mode: string, depth?: number) => void;
  findings: EvidenceFinding[];
}

export const EmailIntelView: React.FC<EmailIntelViewProps> = ({ onStartInvestigation, findings }) => {
  const [email, setEmail] = useState('');

  const emailFindings = findings.filter(f => f.entity_type === 'email' || f.entity_type === 'breach_record');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email.trim()) {
      onStartInvestigation(email.trim(), 'mode_3_email', 2);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="border-b border-[#26364B] pb-4">
        <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Mode 3: Email Intelligence</h1>
        <p className="text-xs text-[#94A3B8]">
          Syntax validation, Mail Exchange (MX) routing, Google Account discovery via GHunt, disposable filtering, and authorized breach exposure analysis.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-xl flex gap-4">
        <div className="relative flex-1">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="target.investigation@domain.org"
            className="w-full bg-[#080D16] border border-[#26364B] focus:border-sky-500 rounded-xl px-4 py-3 pl-11 text-sm text-[#F8FAFC] font-mono focus:outline-none"
          />
          <Mail className="w-5 h-5 text-sky-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        </div>
        <button
          type="submit"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-bold text-xs flex items-center space-x-2 cursor-pointer transition-all"
        >
          <span>Run Email Audit</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      {/* Corroborated Findings Table */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold text-[#F8FAFC] uppercase tracking-wider">
          Corroborated Email & Breach Findings ({emailFindings.length})
        </h2>

        {emailFindings.length > 0 ? (
          <div className="space-y-3">
            {emailFindings.map((f) => (
              <div key={f.id} className="p-4 rounded-xl bg-[#0E1624] border border-[#26364B] space-y-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-sky-400 font-bold">{f.entity_value}</span>
                  <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {f.confidence}
                  </span>
                </div>
                <p className="text-[#CBD5E1]">{f.evidence_description}</p>
                <div className="text-[10px] text-[#64748B]">Source Engine: {f.source_name}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-[#64748B]">
            No email intelligence records in active memory. Execute a query to inspect live MX and exposure feeds.
          </div>
        )}
      </div>
    </div>
  );
};
