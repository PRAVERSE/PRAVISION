import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  AlertTriangle, 
  CheckCircle2, 
  Activity, 
  Skull, 
  Search, 
  ExternalLink,
  Lock,
  Globe
} from 'lucide-react';
import { osintApi } from '../services/api';
import { ThreatPostureResult } from '../types/osint';

export const ThreatIntelView: React.FC = () => {
  const [threat, setThreat] = useState<ThreatPostureResult | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchThreatPosture = async () => {
      try {
        setLoading(true);
        const res = await osintApi.getThreatPosture();
        setThreat(res);
      } catch (err) {
        console.error('Threat posture fetch error:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchThreatPosture();
  }, []);

  const getSeverityColor = (sev: string) => {
    switch (sev) {
      case 'CRITICAL': return 'text-red-500 bg-red-950/40 border-red-800/40';
      case 'HIGH': return 'text-orange-400 bg-orange-950/40 border-orange-800/40';
      case 'MODERATE': return 'text-amber-400 bg-amber-950/40 border-amber-800/40';
      case 'LOW': return 'text-sky-400 bg-sky-950/40 border-sky-800/40';
      default: return 'text-emerald-400 bg-emerald-950/40 border-emerald-800/40';
    }
  };

  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-5 h-5 text-red-400" />
              <h1 className="text-lg font-bold text-white tracking-wide">THREAT INTELLIGENCE &amp; IOC POSTURE</h1>
            </div>
            <p className="text-xs text-slate-400 mt-1">Cross-source malicious indicator screening, internet scanner telemetry, sanctions, and abuse scoring.</p>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-xs text-slate-500">Evaluating threat telemetry across active findings...</div>
        ) : !threat ? (
          <div className="p-12 text-center text-xs text-slate-500">Failed to load threat posture.</div>
        ) : (
          <div className="space-y-6">
            {/* Risk Score & Severity Hero Card */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                <div className="text-center md:text-left">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block mb-1">AGGREGATE RISK SCORE</span>
                  <div className="flex items-baseline space-x-2">
                    <span className="text-4xl font-black font-mono text-white">{threat.overall_risk_score}</span>
                    <span className="text-sm font-mono text-slate-500">/ 100</span>
                  </div>
                  <div className="w-full bg-[#1E293B] h-2 rounded-full mt-3 overflow-hidden">
                    <div 
                      className={`h-full rounded-full transition-all duration-500 ${
                        threat.overall_risk_score >= 75 ? 'bg-red-500' :
                        threat.overall_risk_score >= 50 ? 'bg-orange-500' :
                        threat.overall_risk_score >= 25 ? 'bg-amber-500' :
                        threat.overall_risk_score > 0 ? 'bg-sky-500' : 'bg-emerald-500'
                      }`}
                      style={{ width: `${threat.overall_risk_score}%` }}
                    />
                  </div>
                </div>

                <div className="text-center">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-widest block mb-1">THREAT SEVERITY LEVEL</span>
                  <span className={`inline-block px-4 py-1.5 rounded-full text-xs font-bold border tracking-wider ${getSeverityColor(threat.severity_level)}`}>
                    {threat.severity_level}
                  </span>
                  <span className="block text-[11px] text-slate-500 mt-2">
                    {threat.is_known_malicious ? 'Flagged in active threat feeds' : 'No confirmed malicious payloads'}
                  </span>
                </div>

                <div className="bg-[#131F37] border border-[#1E293B] p-4 rounded-lg text-xs space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Identified Indicators:</span>
                    <span className="font-bold text-white font-mono">{threat.indicators.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Sanctions / Watchlist Hits:</span>
                    <span className="font-bold text-white font-mono">{threat.sanctions_matches.length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Known Adversary Attribution:</span>
                    <span className="font-bold text-sky-400 font-mono">{threat.identified_actors.length > 0 ? threat.identified_actors.join(', ') : 'None'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Identified Threat Indicators */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-5">
              <h2 className="text-sm font-semibold text-white mb-3 flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>IDENTIFIED RISK INDICATORS ({threat.indicators.length})</span>
              </h2>

              {threat.indicators.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 border border-dashed border-[#1E293B] rounded">
                  Zero malicious indicators or abuse flags detected for current target.
                </div>
              ) : (
                <div className="space-y-2">
                  {threat.indicators.map((ind, idx) => (
                    <div key={idx} className="p-3 bg-[#131F37] border border-[#1E293B] rounded-md flex items-center justify-between text-xs">
                      <div className="flex items-center space-x-3">
                        <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-red-950 text-red-300 border border-red-800/40 uppercase">
                          {ind.type}
                        </span>
                        <span className="text-slate-200 font-medium">{ind.detail}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Sanctions & Watchlists */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-5">
              <h2 className="text-sm font-semibold text-white mb-3 flex items-center space-x-2">
                <Lock className="w-4 h-4 text-sky-400" />
                <span>INTERNATIONAL SANCTIONS &amp; WATCHLIST SCREENING ({threat.sanctions_matches.length})</span>
              </h2>

              {threat.sanctions_matches.length === 0 ? (
                <div className="p-6 text-center text-xs text-slate-500 border border-dashed border-[#1E293B] rounded">
                  No hits found on international sanctions, PEP, or denied persons watchlists.
                </div>
              ) : (
                <div className="space-y-2">
                  {threat.sanctions_matches.map((s, idx) => (
                    <div key={idx} className="p-3 bg-[#131F37] border border-[#1E293B] rounded-md flex items-center justify-between text-xs">
                      <div>
                        <span className="font-semibold text-white">{s.entity}</span>
                        <div className="text-[11px] text-slate-400 mt-1">
                          Watchlists: {s.datasets.join(', ')}
                        </div>
                      </div>
                      <span className="font-mono text-xs text-red-400 font-bold">
                        Score: {Math.round(s.score * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
