import React, { useState } from 'react';
import { 
  Wrench, 
  Search, 
  Filter, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  ShieldCheck, 
  ExternalLink, 
  Key, 
  RefreshCw, 
  ToggleLeft, 
  ToggleRight, 
  Layers 
} from 'lucide-react';
import { ConnectorManifest } from '../types/osint';
import { osintApi } from '../services/api';

interface ToolCenterViewProps {
  connectors: ConnectorManifest[];
  onRefresh: () => void;
}

export const ToolCenterView: React.FC<ToolCenterViewProps> = ({ connectors, onRefresh }) => {
  const [search, setSearch] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedHealth, setSelectedHealth] = useState<string>('all');
  const [testingTool, setTestingTool] = useState<string | null>(null);

  const categories = [
    { id: 'all', label: 'All Categories' },
    { id: 'username_social', label: 'Username & Social' },
    { id: 'email', label: 'Email' },
    { id: 'phone', label: 'Phone' },
    { id: 'media_image', label: 'Media & Forensics' },
    { id: 'geographic', label: 'Geographic' },
    { id: 'website_infrastructure', label: 'Website & Infra' },
    { id: 'global_situational', label: 'Global Situational' },
    { id: 'advanced_platforms', label: 'Advanced Platforms' },
    { id: 'restricted_security_research', label: 'Restricted Research' }
  ];

  const filteredConnectors = connectors.filter((c) => {
    const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase()) || 
                          c.display_name.toLowerCase().includes(search.toLowerCase()) ||
                          c.description.toLowerCase().includes(search.toLowerCase());
    const matchesCat = selectedCategory === 'all' || c.category === selectedCategory;
    const matchesHealth = selectedHealth === 'all' || c.health === selectedHealth;
    return matchesSearch && matchesCat && matchesHealth;
  });

  const handleTest = async (name: string) => {
    setTestingTool(name);
    try {
      await osintApi.testConnector(name);
      onRefresh();
    } catch (err) {
      alert(`Test for ${name} failed: ` + err);
    } finally {
      setTestingTool(null);
    }
  };

  const handleToggle = async (name: string, currentEnabled: boolean) => {
    try {
      await osintApi.toggleConnector(name, !currentEnabled);
      onRefresh();
    } catch (err) {
      alert(`Toggle failed: ` + err);
    }
  };

  const getHealthBadge = (health: string) => {
    switch (health) {
      case 'operational':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold uppercase">Fully Operational</span>;
      case 'partial':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 font-bold uppercase">Partial / Modular</span>;
      case 'auth_required':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold uppercase">Auth / Key Required</span>;
      case 'subscription_required':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold uppercase">Subscription Required</span>;
      case 'restricted':
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-bold uppercase">Policy Restricted</span>;
      default:
        return <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-500/10 text-slate-400 border border-slate-500/20 font-bold uppercase">{health}</span>;
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#26364B] pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-[#F8FAFC]">PRAVISION Tool Center &amp; Connector Matrix</h1>
          <p className="text-xs text-[#94A3B8]">
            Complete 89-tool capability matrix (Phase 2 Expanded). Real-time pre-flight verification, authentication status, and safety policy enforcement.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <select
            value={selectedHealth}
            onChange={(e) => setSelectedHealth(e.target.value)}
            className="bg-[#121D2D] border border-[#26364B] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none"
          >
            <option value="all">All Statuses ({connectors.length})</option>
            <option value="operational">Operational</option>
            <option value="config_required">Config Required</option>
            <option value="auth_required">Auth Required</option>
            <option value="subscription_required">Subscription Required</option>
            <option value="restricted">Restricted</option>
            <option value="partial">Partial</option>
          </select>
          <button
            onClick={onRefresh}
            className="flex items-center space-x-1.5 px-4 py-2 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-sky-400 border border-[#26364B] text-xs font-medium cursor-pointer transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Run All Health Checks</span>
          </button>
        </div>
      </div>

      {/* Filters & Search */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
        <div className="relative w-full md:w-80">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by tool name or capability..."
            className="w-full bg-[#121D2D] border border-[#26364B] rounded-xl px-4 py-2 pl-9 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:outline-none"
          />
          <Search className="w-4 h-4 text-sky-400 absolute left-3 top-1/2 -translate-y-1/2" />
        </div>

        {/* Category Pills */}
        <div className="flex flex-wrap gap-1.5">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all cursor-pointer ${
                selectedCategory === cat.id
                  ? 'bg-sky-500 text-white font-semibold'
                  : 'bg-[#121D2D] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B]'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tool Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {filteredConnectors.map((tool) => (
          <div 
            key={tool.name} 
            className="bg-[#121D2D] border border-[#26364B] hover:border-sky-500/40 rounded-2xl p-5 space-y-4 flex flex-col justify-between transition-all shadow-lg"
          >
            <div className="space-y-3">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-sm font-bold text-[#F8FAFC]">{tool.display_name}</h3>
                  <div className="text-[10px] text-[#64748B] font-mono">{tool.name}</div>
                </div>
                {getHealthBadge(tool.health)}
              </div>

              <p className="text-xs text-[#CBD5E1] line-clamp-2 leading-relaxed">
                {tool.description}
              </p>

              {/* Capabilities Chips */}
              <div className="space-y-1.5">
                <span className="text-[10px] font-semibold text-[#94A3B8] uppercase">Capabilities:</span>
                <div className="flex flex-wrap gap-1">
                  {tool.capabilities.slice(0, 3).map((cap) => (
                    <span key={cap} className="text-[9px] px-2 py-0.5 rounded bg-[#0E1624] text-[#CBD5E1] border border-[#26364B] font-mono">
                      {cap.replace(/_/g, ' ')}
                    </span>
                  ))}
                  {tool.capabilities.length > 3 && (
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-[#0E1624] text-[#64748B] font-mono">
                      +{tool.capabilities.length - 3} more
                    </span>
                  )}
                  {tool.restricted_capabilities.length > 0 && (
                    <span className="text-[9px] px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-mono">
                      {tool.restricted_capabilities.length} Restricted
                    </span>
                  )}
                </div>
              </div>

              {tool.last_error && (
                <div className="p-2.5 rounded-lg bg-[#0E1624] border border-amber-500/20 text-[11px] text-amber-300/90 font-mono">
                  {tool.last_error}
                </div>
              )}
            </div>

            {/* Bottom Actions */}
            <div className="pt-3 border-t border-[#26364B] flex items-center justify-between text-xs">
              <a
                href={tool.website_or_repo}
                target="_blank"
                rel="noreferrer"
                className="text-[#94A3B8] hover:text-sky-400 flex items-center space-x-1"
              >
                <span>Docs</span>
                <ExternalLink className="w-3 h-3" />
              </a>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleTest(tool.name)}
                  disabled={testingTool === tool.name}
                  className="px-2.5 py-1 rounded bg-[#0E1624] hover:bg-[#1E293B] text-sky-400 border border-[#26364B] text-[11px] font-semibold cursor-pointer transition-all flex items-center space-x-1"
                >
                  <RefreshCw className={`w-3 h-3 ${testingTool === tool.name ? 'animate-spin' : ''}`} />
                  <span>Test</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

