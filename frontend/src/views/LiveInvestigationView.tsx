import React, { useState } from 'react';
import { 
  Radio, 
  CheckCircle2, 
  Clock, 
  AlertCircle, 
  Activity, 
  Layers, 
  Share2, 
  ChevronDown, 
  ChevronUp, 
  Square, 
  CheckCircle 
} from 'lucide-react';
import { ActiveInvestigation, EvidenceFinding } from '../types/osint';

interface LiveInvestigationViewProps {
  investigation: ActiveInvestigation | null;
  findings: EvidenceFinding[];
  onCancel: () => void;
  onNavigate: (view: string) => void;
}

export const LiveInvestigationView: React.FC<LiveInvestigationViewProps> = ({ 
  investigation, 
  findings, 
  onCancel,
  onNavigate 
}) => {
  const [expandedConnector, setExpandedConnector] = useState<string | null>(null);

  if (!investigation) {
    return (
      <div className="p-12 text-center max-w-xl mx-auto space-y-4">
        <Radio className="w-12 h-12 text-[#26364B] mx-auto" />
        <h2 className="text-xl font-bold text-[#F8FAFC]">No Live Investigation Active</h2>
        <p className="text-sm text-[#94A3B8]">
          Launch an investigation from Universal Search to monitor real-time connector execution, discovery queue expansion, and evidence corroboration.
        </p>
        <button
          onClick={() => onNavigate('search')}
          className="px-5 py-2.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-white font-medium text-xs transition-all cursor-pointer"
        >
          Go to Universal Search
        </button>
      </div>
    );
  }

  const connectorList = Object.values(investigation.connector_statuses);
  const running = connectorList.filter(c => c.status === 'running').length;
  const completed = connectorList.filter(c => c.status === 'completed').length;
  const failed = connectorList.filter(c => c.status === 'failed').length;
  const waiting = connectorList.filter(c => c.status === 'waiting').length;

  const total = connectorList.length || 1;
  const progressPercent = Math.min(100, Math.round(((completed + failed) / total) * 100));

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header telemetry banner */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#26364B] pb-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className={`w-3 h-3 rounded-full ${investigation.status === 'running' ? 'bg-amber-400 animate-ping' : 'bg-emerald-400'}`} />
              <h1 className="text-xl font-extrabold text-[#F8FAFC]">Live Investigation Telemetry</h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#0E1624] text-sky-400 border border-sky-500/20 font-mono">
                {investigation.id.substring(0, 8)}
              </span>
            </div>
            <p className="text-xs text-[#94A3B8]">
              Target: <strong className="text-sky-300 font-mono">{investigation.root_input}</strong> | Mode: <span className="capitalize">{investigation.mode.replace(/_/g, ' ')}</span>
            </p>
          </div>

          <div className="flex items-center space-x-3">
            {investigation.status === 'running' && (
              <button
                onClick={onCancel}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-medium transition-all cursor-pointer"
              >
                <Square className="w-3.5 h-3.5 fill-red-400" />
                <span>Stop Engine</span>
              </button>
            )}
            <button
              onClick={() => onNavigate('graph')}
              className="px-3.5 py-1.5 rounded-lg bg-[#0E1624] hover:bg-[#1E293B] text-sky-400 border border-sky-500/30 text-xs font-medium transition-all cursor-pointer flex items-center space-x-1.5"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>Inspect Graph</span>
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs text-[#94A3B8]">
            <span className="font-semibold text-[#F8FAFC]">Connector Execution Progress: {progressPercent}%</span>
            <span>{completed} of {total} Complete</span>
          </div>
          <div className="w-full h-2.5 rounded-full bg-[#080D16] border border-[#26364B] overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-sky-500 to-indigo-500 transition-all duration-500" 
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {/* Live Counters */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
            <span className="text-xs text-[#94A3B8]">Active Running:</span>
            <span className="text-sm font-bold text-amber-400 font-mono">{running}</span>
          </div>
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
            <span className="text-xs text-[#94A3B8]">Completed:</span>
            <span className="text-sm font-bold text-emerald-400 font-mono">{completed}</span>
          </div>
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
            <span className="text-xs text-[#94A3B8]">Corroborated Findings:</span>
            <span className="text-sm font-bold text-sky-400 font-mono">{investigation.total_findings}</span>
          </div>
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B] flex items-center justify-between">
            <span className="text-xs text-[#94A3B8]">Verified Edges:</span>
            <span className="text-sm font-bold text-indigo-400 font-mono">{investigation.verified_relationships}</span>
          </div>
        </div>
      </div>

      {/* Two column layout: Connector cards & Live Event Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Connector Cards */}
        <div className="lg:col-span-2 space-y-3">
          <h2 className="text-sm font-bold uppercase tracking-wider text-[#94A3B8] flex items-center space-x-2">
            <Layers className="w-4 h-4 text-sky-400" />
            <span>Assigned Investigation Connectors ({connectorList.length})</span>
          </h2>

          <div className="space-y-2 max-h-[580px] overflow-y-auto pr-1">
            {connectorList.map((conn) => {
              const isExpanded = expandedConnector === conn.name;
              return (
                <div 
                  key={conn.name} 
                  className="bg-[#121D2D] border border-[#26364B] rounded-xl overflow-hidden transition-all"
                >
                  <div 
                    onClick={() => setExpandedConnector(isExpanded ? null : conn.name)}
                    className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-[#162336] transition-colors"
                  >
                    <div className="flex items-center space-x-3">
                      {conn.status === 'completed' && <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />}
                      {conn.status === 'running' && <Activity className="w-4 h-4 text-amber-400 animate-spin shrink-0" />}
                      {conn.status === 'failed' && <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />}
                      {conn.status === 'waiting' && <Clock className="w-4 h-4 text-[#64748B] shrink-0" />}

                      <div>
                        <div className="text-xs font-semibold text-[#F8FAFC]">{conn.display_name}</div>
                        <div className="text-[10px] text-[#94A3B8] font-mono">{conn.name}</div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-3">
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                        conn.status === 'completed' ? 'bg-emerald-500/10 text-emerald-400' :
                        conn.status === 'running' ? 'bg-amber-500/10 text-amber-400' :
                        conn.status === 'failed' ? 'bg-rose-500/10 text-rose-400' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {conn.status}
                      </span>
                      <span className="text-[11px] text-[#94A3B8] font-mono">{conn.duration_ms}ms</span>
                      <span className="text-[11px] font-bold text-sky-400 font-mono">+{conn.findings_count}</span>
                      {isExpanded ? <ChevronUp className="w-4 h-4 text-[#94A3B8]" /> : <ChevronDown className="w-4 h-4 text-[#94A3B8]" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="bg-[#0E1624] p-3 text-xs border-t border-[#26364B] space-y-1.5 font-mono text-[#CBD5E1]">
                      <div>Duration: {conn.duration_ms} ms</div>
                      <div>Yielded Findings: {conn.findings_count} verified entities</div>
                      {conn.error_message && (
                        <div className="text-rose-400">Diagnosis: {conn.error_message}</div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Real-time Event Stream */}
        <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-5 flex flex-col h-[640px]">
          <div className="flex items-center space-x-2 border-b border-[#26364B] pb-3 mb-3">
            <Radio className="w-4 h-4 text-sky-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#F8FAFC]">Live Event Log Stream</h2>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 font-mono text-[11px] pr-1">
            {investigation.recent_events.slice().reverse().map((evt, idx) => (
              <div key={idx} className="p-2 rounded bg-[#080D16] border border-[#26364B]/60 space-y-1">
                <div className="flex items-center justify-between text-[#64748B] text-[10px]">
                  <span className="text-sky-400 font-semibold">{evt.type}</span>
                  <span>{evt.timestamp?.split('T')[1]?.split('.')[0]}</span>
                </div>
                <div className="text-[#CBD5E1] break-all">
                  {JSON.stringify(evt.data)}
                </div>
              </div>
            ))}
            {investigation.recent_events.length === 0 && (
              <div className="py-8 text-center text-xs text-[#64748B]">Listening on telemetry websocket stream...</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

