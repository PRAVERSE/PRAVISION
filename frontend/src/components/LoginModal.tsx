import React, { useState } from 'react';
import { 
  Lock, 
  User, 
  Shield, 
  LogOut, 
  AlertCircle, 
  CheckCircle2, 
  X,
  KeyRound,
  ShieldCheck
} from 'lucide-react';
import { UserProfile, UserRole } from '../types/osint';
import { authApi } from '../services/api';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentUser: UserProfile | null;
  onLoginSuccess: (user: UserProfile) => void;
  onLogoutSuccess: () => void;
}

export const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  currentUser,
  onLoginSuccess,
  onLogoutSuccess
}) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!isOpen) return null;

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await authApi.login(username, password);
      onLoginSuccess(res.user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    setLoading(true);
    try {
      await authApi.logout();
      onLogoutSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Logout failed');
    } finally {
      setLoading(false);
    }
  };

  const setRolePreset = (role: UserRole) => {
    setError(null);
    if (role === 'admin') {
      setUsername('admin');
      setPassword('PravisionAdmin2026!');
    } else if (role === 'case_officer') {
      setUsername('case_officer');
      setPassword('PravisionOfficer2026!');
    } else if (role === 'analyst') {
      setUsername('analyst');
      setPassword('PravisionAnalyst2026!');
    }
  };

  const getRoleBadgeColor = (role: UserRole) => {
    switch (role) {
      case 'admin':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      case 'case_officer':
        return 'bg-sky-500/20 text-sky-300 border-sky-500/30';
      case 'analyst':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-[#0E1624] border border-[#26364B] rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="px-6 py-4 bg-[#121D2D] border-b border-[#26364B] flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <ShieldCheck className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#F8FAFC]">PRAVISION Security & RBAC</h3>
              <p className="text-[11px] text-[#94A3B8]">Multi-User Role-Based Access Control</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#1E293B] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5">
          {currentUser ? (
            /* Logged in state */
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-[#121D2D] border border-[#26364B] flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-10 h-10 rounded-full bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 font-bold uppercase">
                    {currentUser.username.substring(0, 2)}
                  </div>
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-semibold text-[#F8FAFC]">{currentUser.username}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${getRoleBadgeColor(currentUser.role)}`}>
                        {currentUser.role.toUpperCase()}
                      </span>
                    </div>
                    <span className="text-xs text-[#94A3B8]">{currentUser.email}</span>
                  </div>
                </div>
              </div>

              <div className="text-xs text-[#94A3B8] bg-[#080D16] p-3 rounded-lg border border-[#26364B]/60 space-y-1">
                <div className="flex justify-between">
                  <span>Account Status:</span>
                  <span className="text-emerald-400 font-medium">Active (Verified)</span>
                </div>
                <div className="flex justify-between">
                  <span>Role Permissions:</span>
                  <span className="text-sky-300 font-mono">
                    {currentUser.role === 'admin' && 'Full System & User Control'}
                    {currentUser.role === 'case_officer' && 'Create, Investigate & Share Cases'}
                    {currentUser.role === 'analyst' && 'View & Analyze Permitted Cases'}
                  </span>
                </div>
              </div>

              <button
                onClick={handleLogout}
                disabled={loading}
                className="w-full py-2.5 rounded-xl bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 font-medium text-xs flex items-center justify-center space-x-2 transition-all cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
                <span>{loading ? 'Revoking Session...' : 'Sign Out Current Session'}</span>
              </button>
            </div>
          ) : (
            /* Login form */
            <form onSubmit={handleLogin} className="space-y-4">
              {error && (
                <div className="p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">Username or Operator ID</label>
                <div className="relative">
                  <User className="w-4 h-4 text-[#64748B] absolute left-3 top-2.5" />
                  <input
                    type="text"
                    required
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="e.g. admin or case_officer"
                    className="w-full pl-9 pr-3 py-2 bg-[#121D2D] border border-[#26364B] rounded-xl text-xs text-[#F8FAFC] placeholder-[#64748B] focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-[#94A3B8] mb-1.5">Passphrase</label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-[#64748B] absolute left-3 top-2.5" />
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter security passphrase"
                    className="w-full pl-9 pr-3 py-2 bg-[#121D2D] border border-[#26364B] rounded-xl text-xs text-[#F8FAFC] placeholder-[#64748B] focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-[#080D16] font-bold text-xs shadow-lg shadow-sky-500/20 flex items-center justify-center space-x-2 transition-all cursor-pointer"
              >
                <KeyRound className="w-4 h-4" />
                <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
              </button>

              {/* Quick Preset Selector for Fast Verification */}
              <div className="pt-2 border-t border-[#26364B]/60">
                <span className="text-[11px] text-[#64748B] block mb-2 text-center">Fast RBAC Role Presets</span>
                <div className="grid grid-cols-3 gap-2">
                  <button
                    type="button"
                    onClick={() => setRolePreset('admin')}
                    className="py-1.5 px-2 rounded-lg bg-purple-500/10 hover:bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-mono font-medium transition-all cursor-pointer text-center"
                  >
                    Admin
                  </button>
                  <button
                    type="button"
                    onClick={() => setRolePreset('case_officer')}
                    className="py-1.5 px-2 rounded-lg bg-sky-500/10 hover:bg-sky-500/20 text-sky-300 border border-sky-500/30 text-[10px] font-mono font-medium transition-all cursor-pointer text-center"
                  >
                    Case Officer
                  </button>
                  <button
                    type="button"
                    onClick={() => setRolePreset('analyst')}
                    className="py-1.5 px-2 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-mono font-medium transition-all cursor-pointer text-center"
                  >
                    Analyst
                  </button>
                </div>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
