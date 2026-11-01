import React, { useState } from 'react';
import { Phone, ArrowRight, ShieldCheck, MapPin, Radio } from 'lucide-react';
import { EvidenceFinding } from '../types/osint';

interface PhoneIntelViewProps {
  onStartInvestigation: (target: string, mode: string, depth?: number) => void;
  findings: EvidenceFinding[];
}

export const PhoneIntelView: React.FC<PhoneIntelViewProps> = ({ onStartInvestigation, findings }) => {
  const [phoneNumber, setPhoneNumber] = useState('');

  const phoneFindings = findings.filter(f => f.entity_type === 'phone' || f.entity_type === 'location_place');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (phoneNumber.trim()) {
      onStartInvestigation(phoneNumber.trim(), 'mode_4_phone', 1);
    }
  };

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      <div className="border-b border-[#26364B] pb-4">
        <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Mode 4: Phone Intelligence</h1>
        <p className="text-xs text-[#94A3B8]">
          E.164 normalization, international carrier allocation, regional timezones, and public directory references via PhoneInfoga and Numverify.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-xl flex gap-4">
        <div className="relative flex-1">
          <input
            type="text"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="+1 202 555 0199 or international format"
            className="w-full bg-[#080D16] border border-[#26364B] focus:border-sky-500 rounded-xl px-4 py-3 pl-11 text-sm text-[#F8FAFC] font-mono focus:outline-none"
          />
          <Phone className="w-5 h-5 text-sky-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
        </div>
        <button
          type="submit"
          className="px-6 py-3 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-bold text-xs flex items-center space-x-2 cursor-pointer transition-all"
        >
          <span>Parse & Lookup</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </form>

      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold text-[#F8FAFC] uppercase tracking-wider">
          Normalized Telecom & Carrier Details ({phoneFindings.length})
        </h2>

        {phoneFindings.length > 0 ? (
          <div className="space-y-3">
            {phoneFindings.map((f) => (
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
            No telecom records loaded. Enter an international or local number to execute E.164 parsing.
          </div>
        )}
      </div>
    </div>
  );
};
