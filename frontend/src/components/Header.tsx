import React from 'react';
import { 
  ShieldAlert, 
  Trash2, 
  Activity, 
  Settings, 
  Search, 
  Layers, 
  FileText,
  User,
  ShieldCheck,
  LogOut
} from 'lucide-react';
import { ActiveInvestigation, UserProfile } from '../types/osint';

interface HeaderProps {
  investigation: ActiveInvestigation | null;
  onClear: () => void;
  onNavigate: (view: string) => void;
  operationalConnectorsCount: number;
  currentUser?: UserProfile | null;
  onOpenLogin?: () => void;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ 
  investigation, 
  onClear, 
  onNavigate,
  operationalConnectorsCount,
  currentUser,
  onOpenLogin,
  onLogout
}) => {
  return (
    <header className="h-16 bg-[#0E1624] border-b border-[#26364B] px-6 flex items-center justify-between sticky top-0 z-40">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-2 cursor-pointer" onClick={() => onNavigate('overview')}>
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-[#38BDF8] to-[#818CF8] flex items-center justify-center shadow-lg shadow-sky-500/20">
            <Layers className="w-5 h-5 text-[#080D16]" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-lg tracking-wider text-[#F8FAFC]">PRAVISION</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">OSINT</span>
            </div>
            <p className="text-[10px] text-[#94A3B8] tracking-tight">Universal Intelligence Platform</p>
          </div>
        </div>

        {/* Status indicator */}
        <div className="h-6 w-[1px] bg-[#26364B]" />

        {investigation ? (
          <div className="flex items-center space-x-2 px-3 py-1 rounded-full bg-[#121D2D] border border-[#26364B]">
            <span className={`w-2 h-2 rounded-full ${investigation.status === 'running' ? 'bg-amber-400 animate-pulse' : 'bg-emerald-400'}`} />
            <span className="text-xs text-[#94A3B8]">Target:</span>
            <span className="text-xs font-mono font-semibold text-[#38BDF8]">{investigation.root_input}</span>
            <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-[#080D16] text-[#94A3B8]">
              {investigation.status}
            </span>
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-xs text-[#94A3B8]">
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span>No Active Investigation (Zero-History Mode)</span>
          </div>
        )}
      </div>

      <div className="flex items-center space-x-3">
        {/* Connector Health pill */}
        <div className="flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-[#121D2D] border border-[#26364B]">
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
          <span className="text-[#94A3B8]">Connectors:</span>
          <span className="font-semibold text-emerald-400">{operationalConnectorsCount} Ready</span>
        </div>

        {/* Clear Investigation */}
        {investigation && (
          <button
            onClick={onClear}
            className="flex items-center space-x-1.5 text-xs px-3 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 transition-all font-medium cursor-pointer"
            title="Eradicate current investigation data from memory"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Investigation</span>
          </button>
        )}

        {/* User / RBAC Profile Button */}
        <button
          onClick={onOpenLogin}
          className="flex items-center space-x-2 text-xs px-2.5 py-1.5 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] border border-[#26364B] transition-all cursor-pointer"
          title={currentUser ? `Logged in as ${currentUser.username} (${currentUser.role})` : 'Sign in to access RBAC features'}
        >
          <div className="w-5 h-5 rounded-full bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
            <User className="w-3 h-3" />
          </div>
          {currentUser ? (
            <div className="flex items-center space-x-1.5">
              <span className="font-medium text-[#F8FAFC]">{currentUser.username}</span>
              <span className={`text-[10px] font-mono px-1.5 py-0.2 rounded border ${
                currentUser.role === 'admin' ? 'bg-purple-500/20 text-purple-300 border-purple-500/30' :
                currentUser.role === 'case_officer' ? 'bg-sky-500/20 text-sky-300 border-sky-500/30' :
                'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
              }`}>
                {currentUser.role.toUpperCase()}
              </span>
            </div>
          ) : (
            <span className="text-[#94A3B8]">Sign In</span>
          )}
        </button>

        {/* Explicit Sign Out Button */}
        {currentUser && onLogout && (
          <button
            id="btn-sign-out"
            onClick={onLogout}
            className="flex items-center space-x-1.5 text-xs px-2.5 py-1.5 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 transition-all cursor-pointer font-medium"
            title="Sign Out of PRAVISION"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sign Out</span>
          </button>
        )}

        {/* Settings button */}
        <button
          onClick={() => onNavigate('settings')}
          className="p-2 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B] transition-all cursor-pointer"
          title="Settings & Privacy"
        >
          <Settings className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};

