import React from 'react';
import { Loader2, ShieldCheck, Activity } from 'lucide-react';

interface ViewLoadingFallbackProps {
  title?: string;
  subtitle?: string;
}

export const ViewLoadingFallback: React.FC<ViewLoadingFallbackProps> = ({
  title = "INITIALIZING INTELLIGENCE MODULE",
  subtitle = "Mounting telemetry pipeline & security sandbox..."
}) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-[#94A3B8] p-8 select-none">
      <div className="relative flex items-center justify-center mb-6">
        {/* Outer pulse ring */}
        <div className="absolute w-20 h-20 rounded-full border border-sky-500/20 animate-ping" />
        <div className="absolute w-16 h-16 rounded-full border border-sky-500/40 animate-pulse" />
        {/* Core spinner */}
        <div className="relative w-12 h-12 rounded-xl bg-[#0D1524] border border-sky-500/50 flex items-center justify-center shadow-lg shadow-sky-950/40">
          <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
        </div>
      </div>

      <div className="text-center space-y-2 max-w-sm">
        <div className="flex items-center justify-center gap-2 text-xs font-mono font-bold tracking-widest text-sky-400">
          <Activity className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
          <span>{title}</span>
        </div>
        <p className="text-xs text-slate-400 font-mono">
          {subtitle}
        </p>
      </div>

      {/* Cyberpunk telemetry bar */}
      <div className="mt-6 w-48 h-1 bg-[#1E293B] rounded-full overflow-hidden">
        <div className="h-full bg-gradient-to-r from-sky-500 via-emerald-400 to-sky-500 animate-pulse w-full" />
      </div>

      <div className="mt-4 flex items-center gap-1.5 text-[10px] text-slate-500 font-mono">
        <ShieldCheck className="w-3 h-3 text-emerald-500/70" />
        <span>PRAVISION ISOLATED VIEW CHUNK</span>
      </div>
    </div>
  );
};

export default ViewLoadingFallback;

