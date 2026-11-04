import React, { useState } from 'react';
import { 
  Lock, 
  User, 
  ShieldCheck, 
  AlertCircle, 
  KeyRound, 
  Eye, 
  EyeOff, 
  Layers,
  Terminal,
  Activity
} from 'lucide-react';
import { UserProfile } from '../types/osint';
import { authApi } from '../services/api';

interface LoginScreenProps {
  onLoginSuccess: (user: UserProfile) => void;
}

export const LoginScreen: React.FC<LoginScreenProps> = ({ onLoginSuccess }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const cleanUser = username.trim();
    const cleanPwd = password;

    if (!cleanUser || !cleanPwd) {
      setError('Username and password are required.');
      return;
    }

    setLoading(true);
    try {
      const res = await authApi.login(cleanUser, cleanPwd);
      onLoginSuccess(res.user);
    } catch (err: any) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-screen bg-[#070B12] text-[#F8FAFC] flex flex-col items-center justify-center p-4 relative overflow-hidden select-none font-sans">
      {/* Background Cyber Grid Effect */}
      <div 
        className="absolute inset-0 opacity-15 pointer-events-none" 
        style={{
          backgroundImage: `radial-gradient(circle at 50% 50%, rgba(56, 189, 248, 0.15) 0%, transparent 60%), linear-gradient(to right, #1E293B 1px, transparent 1px), linear-gradient(to bottom, #1E293B 1px, transparent 1px)`,
          backgroundSize: '100% 100%, 40px 40px, 40px 40px'
        }}
      />

      {/* Login Card Container */}
      <div className="w-full max-w-md bg-[#0E1624] border border-[#26364B] rounded-2xl shadow-2xl shadow-black/80 p-8 relative z-10 backdrop-blur-xl">
        {/* Header with Icon & Title */}
        <div className="flex flex-col items-center text-center mb-7">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-[#38BDF8] via-[#0284C7] to-[#818CF8] flex items-center justify-center shadow-lg shadow-sky-500/25 mb-4 border border-sky-400/30">
            <Layers className="w-7 h-7 text-[#070B12]" />
          </div>
          
          <div className="flex items-center space-x-2.5 mb-1.5">
            <h1 className="text-2xl font-black tracking-widest text-[#F8FAFC] uppercase">PRAVISION</h1>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30 font-semibold tracking-wider">
              ENTERPRISE
            </span>
          </div>
          
          <p className="text-xs text-[#94A3B8] font-medium tracking-tight mb-3">
            Universal OSINT & Intelligence Platform
          </p>

          <div className="flex items-center space-x-2 text-[10px] font-mono px-3 py-1 rounded-full bg-[#121D2D] border border-[#26364B] text-amber-400/90">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
            <span className="tracking-wide">RESTRICTED ACCESS // MANDATORY LOGIN</span>
          </div>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="mb-5 p-3.5 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-xs flex items-start space-x-2.5 animate-fadeIn">
            <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
            <div className="flex-1 font-medium leading-relaxed">
              {error}
            </div>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#CBD5E1] uppercase tracking-wider mb-2">
              Operator Username
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#64748B]">
                <User className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                autoFocus
                placeholder="Enter authorized username"
                className="w-full pl-10 pr-4 py-2.5 bg-[#121D2D] border border-[#26364B] rounded-xl text-sm text-[#F8FAFC] placeholder-[#64748B] focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-all font-mono"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-[#CBD5E1] uppercase tracking-wider mb-2">
              Security Credential
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-[#64748B]">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="Enter password"
                className="w-full pl-10 pr-10 py-2.5 bg-[#121D2D] border border-[#26364B] rounded-xl text-sm text-[#F8FAFC] placeholder-[#64748B] focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-all font-mono"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-[#64748B] hover:text-[#94A3B8] transition-colors cursor-pointer"
                title={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3 px-4 rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white font-semibold text-sm tracking-wide shadow-lg shadow-sky-500/25 transition-all duration-200 flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>VALIDATING IDENTITY...</span>
              </>
            ) : (
              <>
                <KeyRound className="w-4 h-4" />
                <span>ACCESS PLATFORM</span>
              </>
            )}
          </button>
        </form>

        {/* Security Notice */}
        <div className="mt-6 pt-5 border-t border-[#26364B]/60 text-center">
          <p className="text-[10px] text-[#64748B] tracking-tight leading-relaxed">
            Authorized personnel only. All access attempts, analytical queries, and investigation actions are cryptographically signed, timestamped, and retained in immutable audit logs.
          </p>
        </div>
      </div>
    </div>
  );
};

