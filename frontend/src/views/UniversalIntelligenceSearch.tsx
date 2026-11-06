import React, { useState, useEffect, useRef } from 'react';
import { 
  Search, 
  Mail, 
  Phone, 
  User, 
  Image as ImageIcon, 
  Upload, 
  CheckCircle2, 
  AlertCircle, 
  ShieldCheck, 
  ShieldAlert, 
  ExternalLink, 
  Copy, 
  Download, 
  RefreshCw, 
  Clock, 
  Globe, 
  FileText, 
  ChevronRight, 
  Sparkles, 
  X,
  Compass,
  MapPin,
  Layers
} from 'lucide-react';
import { osintApi } from '../services/api';
import { ConsolidatedReport } from '../types/osint';

type SearchMode = 'auto' | 'email' | 'phone' | 'username' | 'image';

export const UniversalIntelligenceSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('auto');
  const [detectedType, setDetectedType] = useState<string>('username');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  
  const [isLoading, setIsLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState<string>('Investigating public sources...');
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ConsolidatedReport | null>(null);
  const [copied, setCopied] = useState(false);
  const [recentSearches, setRecentSearches] = useState<any[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Auto-detect target type based on query input
  useEffect(() => {
    const q = query.trim();
    if (!q) {
      setDetectedType('username');
      return;
    }
    if (q.includes('@') && q.split('@')[1]?.includes('.')) {
      setDetectedType('email');
    } else {
      const digits = q.replace(/[^\d]/g, '');
      if ((q.startsWith('+') && digits.length >= 7) || (digits.length >= 9 && digits.length <= 15 && /^[\d\s\-().+]+$/.test(q))) {
        setDetectedType('phone');
      } else if (/\.(jpg|jpeg|png|webp|gif|tiff|bmp)$/i.test(q)) {
        setDetectedType('image');
      } else {
        setDetectedType('username');
      }
    }
  }, [query]);

  // Load recent searches on mount
  useEffect(() => {
    loadRecentSearches();
  }, []);

  const loadRecentSearches = async () => {
    try {
      const res = await osintApi.getUniversalHistory();
      if (res && res.history) {
        setRecentSearches(res.history);
      }
    } catch {
      // Non-critical background fetch
    }
  };

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setError(null);
    if (file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = (e) => setFilePreview(e.target?.result as string);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setMode('image');
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const clearFile = () => {
    setSelectedFile(null);
    setFilePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleInvestigate = async () => {
    if (mode === 'image' && !selectedFile) {
      setError('Please select or drop an image file to investigate.');
      return;
    }
    if (mode !== 'image' && !query.trim()) {
      setError('Please enter an email, phone number, or username to investigate.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setLoadingStep('Investigating public sources...');

    // Gentle progressive status transitions for user confidence
    const stepTimer1 = setTimeout(() => {
      setLoadingStep('Querying authoritative registries and verified public sources...');
    }, 1200);

    const stepTimer2 = setTimeout(() => {
      setLoadingStep('Correlating identity records and compiling consolidated report...');
    }, 2800);

    try {
      const effectiveType = mode === 'auto' ? detectedType : mode;
      const res = await osintApi.runUniversalInvestigation({
        query: query.trim(),
        type: effectiveType,
        file: mode === 'image' && selectedFile ? selectedFile : undefined
      });

      setReport(res);
      loadRecentSearches();
    } catch (err: any) {
      console.error('Universal investigation error:', err);
      setError(err?.message || 'Investigation could not be completed. Please verify the query and try again.');
    } finally {
      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !isLoading) {
      handleInvestigate();
    }
  };

  const handleCopyReport = () => {
    if (!report) return;
    const textLines = [
      `PRAVISION OSINT INVESTIGATION REPORT`,
      `Target: ${report.target} (${report.target_type.toUpperCase()})`,
      `Status: ${report.status} | Execution Time: ${report.duration_seconds}s`,
      `Timestamp: ${report.timestamp}`,
      `Confidence Score: ${report.confidence_and_verification.score}/100 (${report.confidence_and_verification.overall_level})`,
      ``,
      `SUMMARY:`,
      `Headline: ${report.summary.headline}`,
      `Risk Level: ${report.summary.risk_level}`,
      ...report.summary.key_takeaways.map(t => `- ${t}`),
      ``,
      `IDENTIFIED INFORMATION:`,
      ...Object.entries(report.identified_information).map(([k, v]) => `- ${k}: ${v}`),
      ``
    ];

    if (report.associated_profiles.length > 0) {
      textLines.push(`ASSOCIATED PUBLIC PROFILES:`);
      report.associated_profiles.forEach(p => {
        textLines.push(`- ${p.platform} (${p.identifier}): ${p.url} [${p.status}]`);
      });
      textLines.push(``);
    }

    if (report.contact_associations.length > 0) {
      textLines.push(`CONTACT & IDENTITY ASSOCIATIONS:`);
      report.contact_associations.forEach(c => {
        textLines.push(`- ${c.association_type}: ${c.value} (Source: ${c.source})`);
      });
      textLines.push(``);
    }

    if (report.investigation_limitations.length > 0) {
      textLines.push(`INVESTIGATION LIMITATIONS:`);
      report.investigation_limitations.forEach(l => {
        textLines.push(`- ${l}`);
      });
    }

    navigator.clipboard.writeText(textLines.join('\n'));
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleExportJson = () => {
    if (!report) return;
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `pravision_report_${report.id}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const getRiskBadgeColor = (risk: string) => {
    switch (risk?.toLowerCase()) {
      case 'high':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      case 'medium':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'low':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      default:
        return 'bg-sky-500/10 text-sky-400 border-sky-500/30';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type?.toLowerCase()) {
      case 'email':
        return <Mail className="w-4 h-4 text-sky-400" />;
      case 'phone':
        return <Phone className="w-4 h-4 text-emerald-400" />;
      case 'username':
        return <User className="w-4 h-4 text-indigo-400" />;
      case 'image':
        return <ImageIcon className="w-4 h-4 text-purple-400" />;
      default:
        return <Search className="w-4 h-4 text-slate-400" />;
    }
  };

  return (
    <div className="min-h-full flex flex-col items-center justify-start py-8 px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto space-y-8 select-text">
      
      {/* Platform Title & Purpose */}
      <div className="text-center space-y-2 max-w-2xl">
        <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs font-medium tracking-wide">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Universal Intelligence Search</span>
        </div>
        <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#F8FAFC]">
          Universal OSINT Investigation
        </h1>
        <p className="text-sm sm:text-base text-[#94A3B8]">
          Search any email address, phone number, username, or upload a photograph to generate a consolidated intelligence report.
        </p>
      </div>

      {/* Main Search Panel Card */}
      <div className="w-full bg-[#0E1624] border border-[#26364B] rounded-2xl shadow-2xl p-6 sm:p-8 space-y-6">
        
        {/* Type Selector Tabs */}
        <div className="flex flex-wrap items-center justify-center gap-2 border-b border-[#26364B]/80 pb-4">
          <button
            type="button"
            onClick={() => setMode('auto')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              mode === 'auto'
                ? 'bg-[#1E293B] text-sky-400 border border-sky-500/30 shadow-md'
                : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
            }`}
          >
            <Compass className="w-4 h-4" />
            <span>Auto Detect</span>
          </button>

          <button
            type="button"
            onClick={() => setMode('email')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              mode === 'email'
                ? 'bg-[#1E293B] text-sky-400 border border-sky-500/30 shadow-md'
                : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
            }`}
          >
            <Mail className="w-4 h-4" />
            <span>Email</span>
          </button>

          <button
            type="button"
            onClick={() => setMode('phone')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              mode === 'phone'
                ? 'bg-[#1E293B] text-emerald-400 border border-emerald-500/30 shadow-md'
                : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
            }`}
          >
            <Phone className="w-4 h-4" />
            <span>Phone</span>
          </button>

          <button
            type="button"
            onClick={() => setMode('username')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              mode === 'username'
                ? 'bg-[#1E293B] text-indigo-400 border border-indigo-500/30 shadow-md'
                : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
            }`}
          >
            <User className="w-4 h-4" />
            <span>Username</span>
          </button>

          <button
            type="button"
            onClick={() => setMode('image')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs sm:text-sm font-semibold transition-all ${
              mode === 'image'
                ? 'bg-[#1E293B] text-purple-400 border border-purple-500/30 shadow-md'
                : 'text-[#94A3B8] hover:text-[#F8FAFC] hover:bg-[#121D2D]'
            }`}
          >
            <ImageIcon className="w-4 h-4" />
            <span>Photograph</span>
          </button>
        </div>

        {/* Input Field / File Drag Area */}
        {mode === 'image' ? (
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center space-y-4 transition-all cursor-pointer ${
              selectedFile
                ? 'border-purple-500/50 bg-purple-500/5'
                : 'border-[#26364B] hover:border-purple-500/40 hover:bg-[#121D2D]'
            }`}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files && e.target.files[0] && handleFileSelect(e.target.files[0])}
              accept="image/*"
              className="hidden"
            />

            {filePreview ? (
              <div className="relative group">
                <img
                  src={filePreview}
                  alt="Preview"
                  className="max-h-48 rounded-xl object-contain border border-[#26364B] shadow-lg"
                />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    clearFile();
                  }}
                  className="absolute -top-2 -right-2 p-1.5 rounded-full bg-rose-500 text-white shadow-md hover:bg-rose-600 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <div className="w-16 h-16 rounded-2xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 shadow-inner">
                <Upload className="w-8 h-8" />
              </div>
            )}

            <div className="text-center space-y-1">
              <p className="text-sm font-semibold text-[#F8FAFC]">
                {selectedFile ? selectedFile.name : 'Drag and drop image here or click to browse'}
              </p>
              <p className="text-xs text-[#94A3B8]">
                Supports JPEG, PNG, WebP, TIFF for EXIF, GPS geolocation, and hash verification
              </p>
              {selectedFile && (
                <p className="text-xs text-purple-400 font-mono">
                  {(selectedFile.size / 1024).toFixed(1)} KB
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="relative flex items-center">
            <div className="absolute left-4 flex items-center pointer-events-none">
              {mode === 'auto' ? getTypeIcon(detectedType) : getTypeIcon(mode)}
            </div>

            <input
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setError(null);
              }}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              placeholder={
                mode === 'email'
                  ? 'Enter target email address (e.g., name@domain.com)...'
                  : mode === 'phone'
                  ? 'Enter phone number with or without + (e.g., +14155552671 or 9876543210)...'
                  : mode === 'username'
                  ? 'Enter username or social handle (e.g., torvalds or @elonmusk)...'
                  : 'Enter email, phone, or username to investigate...'
              }
              className="w-full bg-[#080D16] border border-[#26364B] rounded-2xl pl-12 pr-32 py-4 text-[#F8FAFC] placeholder-[#64748B] text-base focus:outline-none focus:border-sky-500 focus:ring-1 focus:ring-sky-500 transition-all font-mono"
            />

            {/* Auto-detect badge */}
            {mode === 'auto' && query.trim() && (
              <div className="absolute right-4 flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-[#121D2D] border border-[#26364B] text-[11px] font-mono text-[#94A3B8]">
                <span className="text-[10px] text-slate-500">TYPE:</span>
                <span className="text-sky-400 font-semibold uppercase">{detectedType}</span>
              </div>
            )}

            {query && !isLoading && (
              <button
                type="button"
                onClick={() => setQuery('')}
                className="absolute right-24 p-1 rounded-lg text-slate-500 hover:text-slate-300 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
        )}

        {/* Primary Action Button */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
          <div className="text-xs text-[#94A3B8] flex items-center space-x-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Ethical OSINT only • Zero credential scraping • 100% server-side execution</span>
          </div>

          <button
            type="button"
            onClick={handleInvestigate}
            disabled={isLoading || (mode === 'image' ? !selectedFile : !query.trim())}
            className={`w-full sm:w-auto px-8 py-3.5 rounded-xl font-bold text-sm tracking-wide flex items-center justify-center space-x-2 transition-all shadow-lg ${
              isLoading || (mode === 'image' ? !selectedFile : !query.trim())
                ? 'bg-[#1E293B] text-slate-500 cursor-not-allowed border border-[#26364B]'
                : 'bg-gradient-to-r from-sky-500 to-indigo-600 hover:from-sky-400 hover:to-indigo-500 text-white shadow-sky-500/25 active:scale-95'
            }`}
          >
            {isLoading ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>Investigating...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Investigate</span>
              </>
            )}
          </button>
        </div>

        {/* Error Notification */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 flex items-start space-x-3 text-rose-300 text-sm animate-fade-in">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="font-semibold">Investigation Alert</p>
              <p className="text-xs text-rose-200/90 mt-0.5">{error}</p>
            </div>
          </div>
        )}

      </div>

      {/* Loading Progress State */}
      {isLoading && (
        <div className="w-full bg-[#0E1624] border border-[#26364B] rounded-2xl p-8 flex flex-col items-center justify-center space-y-4 animate-pulse">
          <div className="relative flex items-center justify-center">
            <div className="w-16 h-16 rounded-full border-4 border-sky-500/20 border-t-sky-500 animate-spin" />
            <div className="absolute w-8 h-8 rounded-full bg-sky-500/10 flex items-center justify-center">
              <Compass className="w-4 h-4 text-sky-400 animate-pulse" />
            </div>
          </div>
          <div className="text-center space-y-1">
            <p className="text-base font-bold text-[#F8FAFC] tracking-wide">
              {loadingStep}
            </p>
            <p className="text-xs text-[#94A3B8]">
              Consolidating public sources, DNS infrastructure, and public platform footprints...
            </p>
          </div>
        </div>
      )}

      {/* Consolidated Final Investigation Report */}
      {report && !isLoading && (
        <div className="w-full space-y-6 animate-fade-in">
          
          {/* Report Top Bar */}
          <div className="bg-[#0E1624] border border-[#26364B] rounded-2xl p-6 sm:p-8 space-y-6 shadow-xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[#26364B] pb-6">
              
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-mono px-2.5 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/30 uppercase font-semibold">
                    {report.target_type}
                  </span>
                  <span className={`text-xs font-mono px-2.5 py-0.5 rounded-full border font-semibold ${getRiskBadgeColor(report.summary.risk_level)}`}>
                    Risk: {report.summary.risk_level}
                  </span>
                  <span className="text-xs font-mono text-slate-400 flex items-center space-x-1">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{report.duration_seconds}s</span>
                  </span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-extrabold text-[#F8FAFC] font-mono break-all">
                  {report.target}
                </h2>
                <p className="text-xs text-[#94A3B8] font-mono">
                  Report ID: {report.id} • {new Date(report.timestamp).toLocaleString()}
                </p>
              </div>

              {/* Confidence Score & Action Buttons */}
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center space-x-3 px-4 py-2.5 rounded-xl bg-[#080D16] border border-[#26364B]">
                  <div className="text-right">
                    <p className="text-[10px] text-slate-400 uppercase font-semibold">Confidence</p>
                    <p className="text-sm font-bold text-sky-400">{report.confidence_and_verification.overall_level}</p>
                  </div>
                  <div className="w-10 h-10 rounded-full bg-sky-500/10 border border-sky-500/30 flex items-center justify-center font-bold text-sm text-sky-400">
                    {report.confidence_and_verification.score}%
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleCopyReport}
                  className="px-4 py-2.5 rounded-xl bg-[#121D2D] hover:bg-[#1E293B] border border-[#26364B] text-slate-300 text-xs font-semibold flex items-center space-x-2 transition-colors"
                >
                  <Copy className="w-4 h-4" />
                  <span>{copied ? 'Copied!' : 'Copy Report'}</span>
                </button>

                <button
                  type="button"
                  onClick={handleExportJson}
                  className="px-4 py-2.5 rounded-xl bg-[#121D2D] hover:bg-[#1E293B] border border-[#26364B] text-slate-300 text-xs font-semibold flex items-center space-x-2 transition-colors"
                >
                  <Download className="w-4 h-4" />
                  <span>Export JSON</span>
                </button>
              </div>
            </div>

            {/* Section 1: Executive Summary */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                <FileText className="w-4 h-4" />
                <span>Executive Summary</span>
              </h3>
              <div className="p-4 rounded-xl bg-[#080D16] border border-[#26364B] space-y-3">
                <p className="text-base font-semibold text-[#F8FAFC]">
                  {report.summary.headline}
                </p>
                {report.summary.key_takeaways.length > 0 && (
                  <ul className="space-y-1.5 pt-1">
                    {report.summary.key_takeaways.map((takeaway, idx) => (
                      <li key={idx} className="text-xs sm:text-sm text-[#94A3B8] flex items-start space-x-2">
                        <CheckCircle2 className="w-4 h-4 text-sky-400 flex-shrink-0 mt-0.5" />
                        <span>{takeaway}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Section 2: Identified Information */}
            {Object.keys(report.identified_information).length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                  <Compass className="w-4 h-4" />
                  <span>Identified Information</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {Object.entries(report.identified_information).map(([key, val], idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-[#080D16] border border-[#26364B] space-y-1"
                    >
                      <p className="text-[11px] font-medium text-slate-400 uppercase tracking-tight">
                        {key}
                      </p>
                      <p className="text-xs sm:text-sm font-semibold text-[#F8FAFC] font-mono break-all">
                        {String(val)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section 3: Associated Public Profiles */}
            {report.associated_profiles.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                  <User className="w-4 h-4" />
                  <span>Associated Public Profiles ({report.associated_profiles.length})</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {report.associated_profiles.map((prof, idx) => (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-[#080D16] border border-[#26364B] flex flex-col justify-between space-y-3 hover:border-sky-500/40 transition-colors"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-center space-x-3">
                          {prof.avatar_url ? (
                            <img
                              src={prof.avatar_url}
                              alt={prof.platform}
                              className="w-10 h-10 rounded-full object-cover border border-[#26364B]"
                            />
                          ) : (
                            <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center font-bold text-sky-400">
                              {prof.platform[0]}
                            </div>
                          )}
                          <div>
                            <p className="text-xs font-bold text-[#F8FAFC]">{prof.platform}</p>
                            <p className="text-xs text-sky-400 font-mono">{prof.identifier}</p>
                          </div>
                        </div>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-mono">
                          {prof.status}
                        </span>
                      </div>

                      {prof.details && (
                        <p className="text-xs text-slate-400 line-clamp-2">
                          {prof.details}
                        </p>
                      )}

                      <a
                        href={prof.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center space-x-1.5 text-xs text-sky-400 hover:text-sky-300 font-semibold pt-1"
                      >
                        <span>View Public Profile</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section 4: Contact & Identity Associations */}
            {report.contact_associations.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                  <MapPin className="w-4 h-4" />
                  <span>Public Identity & Contact Associations</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {report.contact_associations.map((assoc, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-[#080D16] border border-[#26364B] flex items-center justify-between"
                    >
                      <div className="space-y-0.5">
                        <p className="text-[11px] font-medium text-slate-400 uppercase tracking-tight">
                          {assoc.association_type}
                        </p>
                        <p className="text-xs sm:text-sm font-bold text-[#F8FAFC] font-mono">
                          {assoc.value}
                        </p>
                        <p className="text-[10px] text-slate-500">
                          Source: {assoc.source}
                        </p>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#121D2D] text-slate-300 border border-[#26364B] font-mono">
                        {assoc.confidence}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section 5: Relevant Public-Source References */}
            {report.public_references.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                  <Globe className="w-4 h-4" />
                  <span>Relevant Public-Source References</span>
                </h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {report.public_references.map((ref, idx) => (
                    <a
                      key={idx}
                      href={ref.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-3.5 rounded-xl bg-[#080D16] border border-[#26364B] hover:border-sky-500/40 flex items-start justify-between space-x-2 transition-colors group"
                    >
                      <div className="space-y-1 flex-1">
                        <div className="flex items-center space-x-2">
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                            {ref.source_type}
                          </span>
                          <p className="text-xs font-bold text-[#F8FAFC] group-hover:text-sky-300 transition-colors">
                            {ref.title}
                          </p>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-1">
                          {ref.description}
                        </p>
                      </div>
                      <ExternalLink className="w-4 h-4 text-slate-500 group-hover:text-sky-400 transition-colors flex-shrink-0 mt-1" />
                    </a>
                  ))}
                </div>
              </div>
            )}

            {/* Section 6: Related Findings */}
            {report.related_findings.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                  <Layers className="w-4 h-4" />
                  <span>Related Findings & Indicators</span>
                </h3>
                <div className="space-y-2">
                  {report.related_findings.map((finding, idx) => (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-[#080D16] border border-[#26364B] flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                    >
                      <div className="space-y-0.5">
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-[#F8FAFC]">{finding.title}</span>
                          <span className="text-[10px] font-mono text-slate-500">[{finding.category}]</span>
                        </div>
                        <p className="text-xs text-slate-400 font-mono">{finding.details}</p>
                      </div>
                      <span className="self-start sm:self-auto text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {finding.confidence} Confidence
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section 7: Confidence & Verification Breakdown */}
            <div className="space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-sky-400 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4" />
                <span>Confidence & Verification Status</span>
              </h3>
              <div className="p-4 rounded-xl bg-[#080D16] border border-[#26364B] space-y-3">
                <div className="flex items-center justify-between border-b border-[#26364B] pb-3">
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-slate-400">Calculated Intelligence Score:</span>
                    <span className="text-sm font-bold text-sky-400 font-mono">
                      {report.confidence_and_verification.score} / 100 ({report.confidence_and_verification.overall_level})
                    </span>
                  </div>
                  <div className="w-32 bg-[#121D2D] rounded-full h-2 border border-[#26364B]">
                    <div
                      className="bg-gradient-to-r from-sky-500 to-emerald-400 h-2 rounded-full"
                      style={{ width: `${report.confidence_and_verification.score}%` }}
                    />
                  </div>
                </div>

                {report.confidence_and_verification.breakdown.length > 0 && (
                  <div className="space-y-2 pt-1">
                    {report.confidence_and_verification.breakdown.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs">
                        <span className="text-slate-300 font-medium">{item.factor}</span>
                        <div className="flex items-center space-x-2">
                          <span className="text-slate-400">{item.assessment}</span>
                          <span
                            className={`w-2 h-2 rounded-full ${
                              item.impact === 'Positive'
                                ? 'bg-emerald-400'
                                : item.impact === 'Cautionary'
                                ? 'bg-rose-400'
                                : 'bg-slate-400'
                            }`}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Section 8: Investigation Limitations */}
            {report.investigation_limitations.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-bold uppercase tracking-wider text-amber-400 flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4" />
                  <span>Investigation Limitations & Privacy Boundaries</span>
                </h3>
                <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20 space-y-2">
                  <ul className="space-y-1.5">
                    {report.investigation_limitations.map((limit, idx) => (
                      <li key={idx} className="text-xs text-amber-200/90 flex items-start space-x-2">
                        <span className="text-amber-400 font-bold">•</span>
                        <span>{limit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

          </div>
        </div>
      )}

      {/* Recent Investigations Shelf */}
      {recentSearches.length > 0 && !report && !isLoading && (
        <div className="w-full bg-[#0E1624] border border-[#26364B] rounded-2xl p-6 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-2">
            <Clock className="w-4 h-4" />
            <span>Recent Universal Investigations</span>
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {recentSearches.slice(0, 6).map((item, idx) => (
              <div
                key={idx}
                onClick={async () => {
                  try {
                    setIsLoading(true);
                    const fullJob = await osintApi.getUniversalJob(item.id);
                    setReport(fullJob);
                  } catch (e) {
                    console.error(e);
                  } finally {
                    setIsLoading(false);
                  }
                }}
                className="p-3.5 rounded-xl bg-[#080D16] border border-[#26364B] hover:border-sky-500/40 cursor-pointer space-y-1.5 transition-colors group"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 uppercase">
                    {item.target_type}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(item.timestamp).toLocaleDateString()}
                  </span>
                </div>
                <p className="text-xs font-bold text-[#F8FAFC] group-hover:text-sky-300 transition-colors font-mono truncate">
                  {item.target}
                </p>
                <p className="text-[11px] text-slate-400 truncate">
                  {item.headline}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};

