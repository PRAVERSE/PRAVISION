import React from 'react';
import { 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ShieldCheck, 
  Radio, 
  ArrowRight, 
  Key, 
  Cpu, 
  Layers 
} from 'lucide-react';
import { ActiveInvestigation, ConnectorManifest } from '../types/osint';

interface OverviewViewProps {
  investigation: ActiveInvestigation | null;
  connectors: ConnectorManifest[];
  settings: any;
  onNavigate: (view: string) => void;
}

export const OverviewView: React.FC<OverviewViewProps> = ({ 
  investigation, 
  connectors, 
  settings, 
  onNavigate 
}) => {
  const operational = connectors.filter(c => c.health === 'operational').length;
  const partial = connectors.filter(c => c.health === 'partial').length;
  const configAuthReq = connectors.filter(c => ['config_required', 'auth_required', 'subscription_required'].includes(c.health)).length;
  const restricted = connectors.filter(c => c.health === 'restricted').length;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Hero Banner */}
      <div className="relative rounded-2xl bg-gradient-to-r from-[#121D2D] via-[#0E1624] to-[#121D2D] border border-[#26364B] p-8 overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="max-w-2xl relative z-10 space-y-3">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
            <span>PRAVISION ENGINE v1.0.0 — LOCAL INTELLIGENCE</span>
          </div>
          <h1 className="text-3xl font-extrabold text-[#F8FAFC] tracking-tight">
            See Everything. Connect Everything. Understand Everything.
          </h1>
          <p className="text-sm text-[#94A3B8] leading-relaxed">
            Universal OSINT orchestration platform with multi-tool recursive discovery, automated classification, evidence-backed relationship graph topology, and strict memory-only privacy controls.
          </p>
          <div className="pt-2 flex items-center space-x-4">
            <button
              onClick={() => onNavigate('search')}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-sky-500/25 transition-all cursor-pointer"
            >
              <span>Launch New Investigation</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => onNavigate('tool_center')}
              className="px-4 py-2.5 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B] text-xs font-medium transition-all cursor-pointer"
            >
              Inspect Tool Registry ({connectors.length})
            </button>
          </div>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-5">
        <div className="bg-[#121D2D] border border-[#26364B] rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between text-[#94A3B8]">
            <span className="text-xs uppercase font-semibold tracking-wider">Fully Operational</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-bold text-emerald-400">{operational}</div>
          <p className="text-[11px] text-[#94A3B8]">Connectors ready for immediate zero-config execution</p>
        </div>

        <div className="bg-[#121D2D] border border-[#26364B] rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between text-[#94A3B8]">
            <span className="text-xs uppercase font-semibold tracking-wider">Partial / Modular</span>
            <Activity className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-3xl font-bold text-sky-400">{partial}</div>
          <p className="text-[11px] text-[#94A3B8]">Operating via native asynchronous probe engines</p>
        </div>

        <div className="bg-[#121D2D] border border-[#26364B] rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between text-[#94A3B8]">
            <span className="text-xs uppercase font-semibold tracking-wider">Auth / Key Required</span>
            <Key className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-bold text-amber-400">{configAuthReq}</div>
          <p className="text-[11px] text-[#94A3B8]">Optional commercial keys (Shodan, HIBP, Hunter)</p>
        </div>

        <div className="bg-[#121D2D] border border-[#26364B] rounded-xl p-5 space-y-2">
          <div className="flex items-center justify-between text-[#94A3B8]">
            <span className="text-xs uppercase font-semibold tracking-wider">Policy Restricted</span>
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-3xl font-bold text-indigo-400">{restricted}</div>
          <p className="text-[11px] text-[#94A3B8]">Offensive/biometric modules strictly locked</p>
        </div>
      </div>

      {/* Active Session & Engine Status */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Active Investigation Card */}
        <div className="lg:col-span-2 bg-[#121D2D] border border-[#26364B] rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-[#26364B] pb-4">
            <div className="flex items-center space-x-2">
              <Radio className={`w-5 h-5 ${investigation ? 'text-amber-400 animate-pulse' : 'text-[#94A3B8]'}`} />
              <h2 className="text-base font-semibold text-[#F8FAFC]">Active Investigation Lifecycle</h2>
            </div>
            {investigation && (
              <button
                onClick={() => onNavigate('live')}
                className="text-xs text-sky-400 hover:text-sky-300 font-medium flex items-center space-x-1"
              >
                <span>View Live Execution</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {investigation ? (
            <div className="space-y-4">
              <div className="grid grid-cols-3 gap-4 bg-[#0E1624] p-4 rounded-lg border border-[#26364B]">
                <div>
                  <span className="text-[11px] text-[#94A3B8] uppercase">Target Identifier</span>
                  <div className="text-sm font-mono font-bold text-sky-400 truncate">{investigation.root_input}</div>
                </div>
                <div>
                  <span className="text-[11px] text-[#94A3B8] uppercase">Mode</span>
                  <div className="text-sm font-semibold text-[#F8FAFC] capitalize">{investigation.mode.replace(/_/g, ' ')}</div>
                </div>
                <div>
                  <span className="text-[11px] text-[#94A3B8] uppercase">Status</span>
                  <div className="text-sm font-bold text-emerald-400 uppercase">{investigation.status}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
                  <span className="text-xs text-[#94A3B8]">Corroborated Findings:</span>
                  <span className="text-sm font-mono font-bold text-[#F8FAFC]">{investigation.total_findings}</span>
                </div>
                <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
                  <span className="text-xs text-[#94A3B8]">Relational Graph Edges:</span>
                  <span className="text-sm font-mono font-bold text-sky-400">{investigation.verified_relationships}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-12 text-center space-y-2">
              <Layers className="w-10 h-10 text-[#26364B] mx-auto" />
              <p className="text-sm text-[#94A3B8]">No active investigation currently held in memory.</p>
              <p className="text-xs text-[#64748B]">In compliance with zero-persistence directives, past targets are never recorded to disk.</p>
            </div>
          )}
        </div>

        {/* System & Limits Status */}
        <div className="bg-[#121D2D] border border-[#26364B] rounded-xl p-6 space-y-4">
          <div className="flex items-center space-x-2 border-b border-[#26364B] pb-4">
            <Cpu className="w-5 h-5 text-sky-400" />
            <h2 className="text-base font-semibold text-[#F8FAFC]">Engine Limits & Bounds</h2>
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between py-1.5 border-b border-[#26364B]/50">
              <span className="text-[#94A3B8]">Max Recursion Depth:</span>
              <span className="font-mono text-[#F8FAFC] font-semibold">{settings?.limits?.max_depth || 2} Levels</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-[#26364B]/50">
              <span className="text-[#94A3B8]">Max Discovered Entities:</span>
              <span className="font-mono text-[#F8FAFC] font-semibold">{settings?.limits?.max_discovered_entities || 150}</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-[#26364B]/50">
              <span className="text-[#94A3B8]">Connector Timeout:</span>
              <span className="font-mono text-[#F8FAFC] font-semibold">{settings?.limits?.connector_timeout_seconds || 35}s</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-[#26364B]/50">
              <span className="text-[#94A3B8]">Persistent History:</span>
              <span className="font-mono text-emerald-400 font-semibold">DISABLED (Strict In-Memory)</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-[#94A3B8]">GHunt 2.3.4 Integration:</span>
              <span className="font-mono text-emerald-400 font-semibold">Active (~/.malfrats)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
