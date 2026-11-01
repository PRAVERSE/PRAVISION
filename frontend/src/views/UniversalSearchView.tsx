import React, { useState, useEffect } from 'react';
import { 
  Search, 
  Upload, 
  ShieldAlert, 
  CheckCircle2, 
  Layers, 
  Sliders, 
  AlertCircle, 
  ArrowRight, 
  FileUp, 
  Globe2, 
  Mail, 
  Phone, 
  User, 
  MapPin, 
  FileCode 
} from 'lucide-react';
import { osintApi } from '../services/api';
import { ClassifiedInput } from '../types/osint';

interface UniversalSearchViewProps {
  onStartInvestigation: (target: string, mode?: string, depth?: number) => void;
  onNavigate: (view: string) => void;
}

export const UniversalSearchView: React.FC<UniversalSearchViewProps> = ({ 
  onStartInvestigation, 
  onNavigate 
}) => {
  const [inputVal, setInputVal] = useState('');
  const [classification, setClassification] = useState<ClassifiedInput | null>(null);
  const [isClassifying, setIsClassifying] = useState(false);
  const [depth, setDepth] = useState(2);
  const [selectedMode, setSelectedMode] = useState<string>('auto');
  const [authConfirmed, setAuthConfirmed] = useState(false);
  const [isStarting, setIsStarting] = useState(false);

  // Debounced auto-classification
  useEffect(() => {
    if (!inputVal.trim()) {
      setClassification(null);
      return;
    }
    const timer = setTimeout(async () => {
      setIsClassifying(true);
      try {
        const res = await osintApi.classify(inputVal.trim());
        setClassification(res);
      } catch (err) {
        console.error(err);
      } finally {
        setIsClassifying(false);
      }
    }, 350);

    return () => clearTimeout(timer);
  }, [inputVal]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      try {
        const uploadRes = await osintApi.uploadMedia(file);
        setInputVal(uploadRes.file_path);
      } catch (err) {
        alert('File upload failed: ' + err);
      }
    }
  };

  const handleLaunch = () => {
    if (!inputVal.trim()) return;
    if (classification?.requires_authorization_confirmation && !authConfirmed) {
      alert('Please confirm authorization for this target category before launching.');
      return;
    }
    setIsStarting(true);
    const targetMode = selectedMode === 'auto' ? classification?.mode : selectedMode;
    onStartInvestigation(inputVal.trim(), targetMode, depth);
  };

  const quickExamples = [
    { label: "Handle: @jack", val: "jack" },
    { label: "Email: test@proton.me", val: "test@proton.me" },
    { label: "Domain: cloudflare.com", val: "cloudflare.com" },
    { label: "Coords: 51.5074, -0.1278", val: "51.5074, -0.1278" },
    { label: "IP: 1.1.1.1", val: "1.1.1.1" }
  ];

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-8">
      {/* Title */}
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-extrabold text-[#F8FAFC] tracking-tight">
          Universal Investigation Intake
        </h1>
        <p className="text-sm text-[#94A3B8]">
          Submit any username, email, phone number, domain, IP address, coordinates, or media file.
        </p>
      </div>

      {/* Main Search Input Box */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 shadow-2xl space-y-4">
        <div className="relative">
          <input
            type="text"
            value={inputVal}
            onChange={(e) => setInputVal(e.target.value)}
            placeholder="Enter username, email, phone, domain, IP, GPS coordinates, or media path..."
            className="w-full bg-[#080D16] border border-[#26364B] focus:border-sky-500 rounded-xl px-5 py-4 pl-12 text-base text-[#F8FAFC] placeholder-[#64748B] focus:outline-none transition-all font-mono"
          />
          <Search className="w-5 h-5 text-sky-400 absolute left-4 top-1/2 -translate-y-1/2" />

          {/* Upload Button */}
          <label className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B] cursor-pointer transition-all" title="Upload Media or Document">
            <Upload className="w-4 h-4" />
            <input type="file" onChange={handleFileUpload} className="hidden" />
          </label>
        </div>

        {/* Quick Examples */}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          <span className="text-xs text-[#64748B]">Quick Pre-fills:</span>
          {quickExamples.map((ex) => (
            <button
              key={ex.label}
              onClick={() => setInputVal(ex.val)}
              className="text-xs px-2.5 py-1 rounded bg-[#0E1624] hover:bg-[#1E293B] text-[#94A3B8] hover:text-sky-300 border border-[#26364B] transition-all cursor-pointer font-mono"
            >
              {ex.label}
            </button>
          ))}
        </div>

        {/* Dynamic Classification Preview */}
        {classification && (
          <div className="bg-[#0E1624] border border-[#26364B] rounded-xl p-4 space-y-3 mt-4">
            <div className="flex items-center justify-between border-b border-[#26364B] pb-2">
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold text-[#F8FAFC]">Automatically Classified Entity:</span>
                <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 uppercase">
                  {classification.detected_type}
                </span>
              </div>
              <span className="text-xs text-[#94A3B8] capitalize">Mode: {classification.mode.replace(/_/g, ' ')}</span>
            </div>

            <div className="text-xs text-[#CBD5E1] space-y-1.5">
              <div><strong className="text-[#94A3B8]">Planned Connectors:</strong> {classification.recommended_connectors.join(', ')}</div>
              <div><strong className="text-[#94A3B8]">Investigation Scope:</strong> {classification.expected_scope}</div>
            </div>

            {classification.requires_authorization_confirmation && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs space-y-2">
                <div className="flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                  <span className="font-semibold">Compliance & Authorization Check</span>
                </div>
                <p className="text-[11px] text-amber-200/80">{classification.authorization_note}</p>
                <label className="flex items-center space-x-2 cursor-pointer pt-1">
                  <input
                    type="checkbox"
                    checked={authConfirmed}
                    onChange={(e) => setAuthConfirmed(e.target.checked)}
                    className="rounded bg-[#080D16] border-[#26364B] text-sky-500 focus:ring-0"
                  />
                  <span className="text-xs font-medium text-[#F8FAFC]">I confirm this investigation is for lawful, authorized public OSINT analysis.</span>
                </label>
              </div>
            )}
          </div>
        )}

        {/* Controls: Depth and Mode */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="bg-[#0E1624] p-3 rounded-xl border border-[#26364B] space-y-1">
            <div className="flex items-center justify-between text-xs text-[#94A3B8]">
              <span>Recursive Exploration Depth:</span>
              <span className="font-bold text-sky-400 font-mono">{depth} {depth === 1 ? 'Level (Direct)' : 'Levels (Recursive)'}</span>
            </div>
            <input
              type="range"
              min="1"
              max="4"
              value={depth}
              onChange={(e) => setDepth(Number(e.target.value))}
              className="w-full accent-sky-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-[#64748B]">
              <span>1: Direct Only</span>
              <span>2: Primary Corroboration</span>
              <span>3: Deep Expansion</span>
              <span>4: Comprehensive</span>
            </div>
          </div>

          <div className="bg-[#0E1624] p-3 rounded-xl border border-[#26364B] space-y-1">
            <span className="text-xs text-[#94A3B8] block">Investigation Mode:</span>
            <select
              value={selectedMode}
              onChange={(e) => setSelectedMode(e.target.value)}
              className="w-full bg-[#121D2D] border border-[#26364B] rounded-lg px-3 py-1.5 text-xs text-[#F8FAFC] focus:outline-none"
            >
              <option value="auto">Auto-Detect from Target Input (Recommended)</option>
              <option value="mode_1_identity">Mode 1: Public Identity Intelligence</option>
              <option value="mode_2_media">Mode 2: Media & Document Intelligence</option>
              <option value="mode_3_email">Mode 3: Email Intelligence</option>
              <option value="mode_4_phone">Mode 4: Phone Intelligence</option>
              <option value="mode_5_website_domain">Mode 5: Website & Domain Intelligence</option>
              <option value="mode_6_organization_asset">Mode 6: Organization & Asset Intelligence</option>
              <option value="mode_7_global_situational">Mode 7: Global Situational Intelligence</option>
            </select>
          </div>
        </div>

        {/* Launch Button */}
        <button
          onClick={handleLaunch}
          disabled={!inputVal.trim() || isStarting}
          className="w-full py-4 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 disabled:opacity-50 text-white font-bold text-sm tracking-wide shadow-xl shadow-sky-500/20 transition-all flex items-center justify-center space-x-2 cursor-pointer"
        >
          <span>{isStarting ? 'Orchestrating Connectors...' : 'Execute PRAVISION Investigation'}</span>
          <ArrowRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
