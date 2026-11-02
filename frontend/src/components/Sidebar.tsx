import React, { useState } from 'react';
import { 
  LayoutDashboard, 
  Search, 
  Radio, 
  Share2, 
  Globe, 
  Image, 
  Mail, 
  User, 
  Phone, 
  Globe2, 
  Server, 
  Wrench, 
  FileText, 
  Settings, 
  FolderLock,
  Clock,
  ShieldAlert,
  Database,
  HardDrive,
  Bot,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';

interface SidebarProps {
  currentView: string;
  onNavigate: (view: string) => void;
  hasActiveInvestigation: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  currentView, 
  onNavigate,
  hasActiveInvestigation 
}) => {
  const [collapsed, setCollapsed] = useState(false);

  const navItems = [
    // Mission Control
    { id: 'command_center', label: 'Command Center', icon: LayoutDashboard },
    { id: 'search', label: 'Universal Intake', icon: Search, highlight: true },
    { id: 'live', label: 'Live Investigation', icon: Radio, badge: hasActiveInvestigation ? 'Active' : null },
    { id: 'cases', label: 'Case Dossiers', icon: FolderLock },

    // Analytical Workspaces
    { id: 'graph', label: 'Gotham Link Graph', icon: Share2 },
    { id: 'map', label: 'Global Tactical Map', icon: Globe },
    { id: 'timeline', label: 'Timeline Analysis', icon: Clock },
    { id: 'threat_intel', label: 'Threat Intel & IOCs', icon: ShieldAlert },
    { id: 'entity_db', label: 'Entity Database', icon: Database },
    { id: 'evidence_vault', label: 'Evidence Center', icon: HardDrive },
    { id: 'ai_assistant', label: 'AI Intelligence Copilot', icon: Bot },
    
    // Domain specific modes
    { id: 'image_intel', label: 'Image Forensics', icon: Image },
    { id: 'email_intel', label: 'Email Intelligence', icon: Mail },
    { id: 'username_intel', label: 'Username Intelligence', icon: User },
    { id: 'phone_intel', label: 'Phone Intelligence', icon: Phone },
    { id: 'website_intel', label: 'Domain & Web Intel', icon: Globe2 },
    { id: 'infra_intel', label: 'Infrastructure Recon', icon: Server },
    
    // Tools, Reports, Settings
    { id: 'tool_center', label: 'Tool Center (89)', icon: Wrench },
    { id: 'reports', label: 'Reports & Export', icon: FileText },
    { id: 'settings', label: 'System Admin', icon: Settings }
  ];

  return (
    <aside 
      className={`${collapsed ? 'w-20' : 'w-64'} bg-[#0E1624] border-r border-[#26364B] flex flex-col transition-all duration-300 select-none z-30 shrink-0`}
    >
      <div className="flex-1 py-4 overflow-y-auto space-y-1 px-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center ${collapsed ? 'justify-center px-0' : 'px-3'} py-2.5 rounded-lg text-xs font-medium transition-all group relative cursor-pointer ${
                isActive 
                  ? 'bg-gradient-to-r from-sky-500/20 to-indigo-500/10 text-sky-400 border border-sky-500/30' 
                  : item.highlight 
                    ? 'bg-sky-500/10 text-sky-300 hover:bg-sky-500/15 border border-sky-500/20' 
                    : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-sky-400' : 'text-[#94A3B8] group-hover:text-[#F8FAFC]'}`} />
              
              {!collapsed && (
                <span className="ml-3 truncate">{item.label}</span>
              )}

              {!collapsed && item.badge && (
                <span className="ml-auto text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-mono">
                  {item.badge}
                </span>
              )}

              {/* Tooltip on collapsed */}
              {collapsed && (
                <div className="absolute left-full ml-3 px-2.5 py-1 bg-[#121D2D] text-[#F8FAFC] text-xs rounded-md shadow-xl border border-[#26364B] opacity-0 pointer-events-none group-hover:opacity-100 transition-opacity whitespace-nowrap z-50">
                  {item.label}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* Collapse toggle */}
      <div className="p-3 border-t border-[#26364B]">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center p-2 rounded-lg bg-[#121D2D] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B] transition-all cursor-pointer"
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          {!collapsed && <span className="ml-2 text-xs">Collapse Navigation</span>}
        </button>
      </div>
    </aside>
  );
};

