import React from 'react';
import { 
  Radio, 
  Search, 
  Share2, 
  Globe, 
  FolderLock, 
  ShieldAlert, 
  HardDrive, 
  Clock, 
  Database, 
  Zap, 
  ArrowRight,
  Bot
} from 'lucide-react';
import { ActiveInvestigation, EvidenceFinding, IntelligenceGraph } from '../types/osint';

interface CommandCenterViewProps {
  activeInvestigation: ActiveInvestigation | null;
  findings: EvidenceFinding[];
  graph: IntelligenceGraph;
  onNavigate: (view: string) => void;
}

export const CommandCenterView: React.FC<CommandCenterViewProps> = ({
  activeInvestigation,
  findings,
  graph,
  onNavigate
}) => {
  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Banner Hero */}
        <div className="bg-gradient-to-r from-[#0F172A] via-[#101B33] to-[#0A1020] border border-[#1E293B] rounded-xl p-6 relative overflow-hidden shadow-2xl">
          <div className="absolute top-0 right-0 w-80 h-80 bg-sky-500/5 rounded-full blur-3xl pointer-events-none" />
          
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center space-x-2 text-sky-400 font-mono text-xs mb-2">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-bold tracking-widest">PRAVISION WORKSTATION — GOTHAM INTELLIGENCE ENGINE</span>
              </div>
              <h1 className="text-2xl font-black text-white tracking-tight">
                See Everything. Connect Everything. Understand Everything.
              </h1>
              <p className="text-xs text-slate-400 mt-1 max-w-xl">
                Universal OSINT analytical suite with recursive cross-source discovery, topological link graph analytics, and evidence-grounded assessment.
              </p>
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              <button
                onClick={() => onNavigate('search')}
                className="flex items-center space-x-2 px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold shadow-lg transition cursor-pointer"
              >
                <Search className="w-4 h-4" />
                <span>New Investigation</span>
              </button>
              <button
                onClick={() => onNavigate('cases')}
                className="flex items-center space-x-2 px-3.5 py-2 bg-[#131F37] hover:bg-[#1E293B] border border-[#1E293B] text-slate-200 rounded-lg text-xs font-semibold transition cursor-pointer"
              >
                <FolderLock className="w-4 h-4 text-sky-400" />
                <span>Case Dossiers</span>
              </button>
            </div>
          </div>
        </div>

        {/* Live Metrics Quad */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div 
            onClick={() => onNavigate('live')}
            className="bg-[#0F172A] border border-[#1E293B] hover:border-sky-500/50 p-4 rounded-lg cursor-pointer transition select-none"
          >
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-[10px] font-mono uppercase">Investigation State</span>
              <Radio className={`w-4 h-4 ${activeInvestigation ? 'text-emerald-400' : 'text-slate-500'}`} />
            </div>
            <div className="text-lg font-bold text-white capitalize font-mono">
              {activeInvestigation ? activeInvestigation.status : 'Idle'}
            </div>
            <span className="text-[10px] text-slate-500">
              {activeInvestigation ? activeInvestigation.root_input : 'Ready for input'}
            </span>
          </div>

          <div 
            onClick={() => onNavigate('entity_db')}
            className="bg-[#0F172A] border border-[#1E293B] hover:border-sky-500/50 p-4 rounded-lg cursor-pointer transition select-none"
          >
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-[10px] font-mono uppercase">Discovered Evidence</span>
              <Database className="w-4 h-4 text-sky-400" />
            </div>
            <div className="text-lg font-bold text-sky-400 font-mono">
              {findings.length} findings
            </div>
            <span className="text-[10px] text-slate-500">
              Across registered connectors
            </span>
          </div>

          <div 
            onClick={() => onNavigate('graph')}
            className="bg-[#0F172A] border border-[#1E293B] hover:border-purple-500/50 p-4 rounded-lg cursor-pointer transition select-none"
          >
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-[10px] font-mono uppercase">Relational Topology</span>
              <Share2 className="w-4 h-4 text-purple-400" />
            </div>
            <div className="text-lg font-bold text-purple-400 font-mono">
              {graph.nodes.length} Nodes / {graph.edges.length} Edges
            </div>
            <span className="text-[10px] text-slate-500">
              NetworkX Graph Engine
            </span>
          </div>

          <div 
            onClick={() => onNavigate('threat_intel')}
            className="bg-[#0F172A] border border-[#1E293B] hover:border-red-500/50 p-4 rounded-lg cursor-pointer transition select-none"
          >
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-[10px] font-mono uppercase">Threat Telemetry</span>
              <ShieldAlert className="w-4 h-4 text-red-400" />
            </div>
            <div className="text-lg font-bold text-white font-mono">
              IOC Guard
            </div>
            <span className="text-[10px] text-slate-500">
              GreyNoise, AbuseIPDB, Sanctions
            </span>
          </div>
        </div>

        {/* Workstation Analytical Modules Grid */}
        <div>
          <h2 className="text-xs font-mono uppercase text-slate-400 tracking-wider mb-3">
            ANALYTICAL WORKSPACES
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div 
              onClick={() => onNavigate('graph')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-sky-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <Share2 className="w-5 h-5 text-sky-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-sky-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">Gotham Relational Graph</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                NetworkX-powered centrality analysis, community partitioning, shortest-path tracing, and Gephi GEXF exports.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('map')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-emerald-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <Globe className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">Global Tactical Map</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                High-contrast geospatial view tracking aircraft (OpenSky), vessels (AIS), seismic activity (USGS), and thermal anomalies.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('timeline')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-amber-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <Clock className="w-5 h-5 text-amber-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-amber-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">Chronological Timeline</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Multi-timestamp event sequencing, infrastructure observation timelines, and automatic activity burst detection.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('threat_intel')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-red-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <ShieldAlert className="w-5 h-5 text-red-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-red-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">Threat Intelligence &amp; IOCs</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Adversary screening, scanner classification, AbuseIPDB confidence checks, and OpenSanctions watchlist checks.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('ai_assistant')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-indigo-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <Bot className="w-5 h-5 text-indigo-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-indigo-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">AI Analytical Copilot</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Evidence-grounded executive briefings, hypothesis generation, analytical gap detection, and grounded interactive QA.
              </p>
            </div>

            <div 
              onClick={() => onNavigate('evidence_vault')}
              className="p-4 bg-[#0F172A] border border-[#1E293B] hover:border-emerald-500/50 rounded-lg cursor-pointer transition group"
            >
              <div className="flex items-center justify-between mb-2">
                <HardDrive className="w-5 h-5 text-emerald-400 group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-emerald-400 transition" />
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">Evidence Vault &amp; Custody</h3>
              <p className="text-[11px] text-slate-400 leading-relaxed">
                Backblaze B2 S3 storage, SHA-256 cryptographic chain of custody, and persistent PostgreSQL / SQLite storage telemetry.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

