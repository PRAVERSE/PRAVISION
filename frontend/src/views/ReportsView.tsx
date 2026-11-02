import React, { useState } from 'react';
import { 
  FileText, 
  Download, 
  FileCode, 
  FileSpreadsheet, 
  CheckCircle2, 
  ExternalLink, 
  ShieldCheck 
} from 'lucide-react';
import { ActiveInvestigation, EvidenceFinding, IntelligenceGraph } from '../types/osint';
import { osintApi } from '../services/api';

interface ReportsViewProps {
  investigation: ActiveInvestigation | null;
  findings: EvidenceFinding[];
  graph: IntelligenceGraph;
}

export const ReportsView: React.FC<ReportsViewProps> = ({ 
  investigation, 
  findings, 
  graph 
}) => {
  const [isExporting, setIsExporting] = useState<string | null>(null);

  const handleDownload = async (format: 'html' | 'pdf' | 'json') => {
    setIsExporting(format);
    try {
      const blob = await osintApi.exportReport(format);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `pravision_dossier_${investigation?.id || 'export'}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      alert(`Export error: ${err}`);
    } finally {
      setIsExporting(null);
    }
  };

  if (!investigation) {
    return (
      <div className="p-12 text-center max-w-xl mx-auto space-y-4">
        <FileText className="w-12 h-12 text-[#26364B] mx-auto" />
        <h2 className="text-xl font-bold text-[#F8FAFC]">No Investigation Report Available</h2>
        <p className="text-sm text-[#94A3B8]">
          In compliance with zero-persistence directives, reports are synthesized on demand only while an active investigation is held in volatile memory.
        </p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header and Download Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#26364B] pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Synthesized Intelligence Dossier</h1>
          <p className="text-xs text-[#94A3B8]">
            Multi-source corroboration report for <strong className="text-sky-300 font-mono">{investigation.root_input}</strong>
          </p>
        </div>

        {/* Export Buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => handleDownload('html')}
            disabled={isExporting !== null}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-sky-500 hover:bg-sky-400 text-white text-xs font-semibold shadow-lg shadow-sky-500/20 cursor-pointer transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export HTML</span>
          </button>
          <button
            onClick={() => handleDownload('pdf')}
            disabled={isExporting !== null}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-sky-400 border border-[#26364B] text-xs font-semibold cursor-pointer transition-all"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Export PDF</span>
          </button>
          <button
            onClick={() => handleDownload('json')}
            disabled={isExporting !== null}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-[#121D2D] hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] border border-[#26364B] text-xs font-semibold cursor-pointer transition-all"
          >
            <FileCode className="w-3.5 h-3.5" />
            <span>JSON</span>
          </button>
        </div>
      </div>

      {/* Executive Summary Card */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-sky-400 border-b border-[#26364B] pb-2">
          Executive Summary
        </h2>
        <p className="text-xs text-[#CBD5E1] leading-relaxed">
          Target identifier <strong>{investigation.root_input}</strong> was investigated under {investigation.mode}. 
          The recursive engine traversed up to depth {investigation.depth}, querying independent open registries, Certificate Transparency logs, 
          authoritative DNS servers, and social platforms. A total of <strong>{findings.length} findings</strong> were verified, producing 
          <strong> {investigation.verified_relationships} corroborated relationships</strong> in the intelligence graph.
        </p>

        <div className="grid grid-cols-3 gap-4 pt-2">
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B]">
            <span className="text-[10px] text-[#64748B] uppercase font-bold">Investigation ID</span>
            <div className="text-xs font-mono font-semibold text-[#F8FAFC]">{investigation.id}</div>
          </div>
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B]">
            <span className="text-[10px] text-[#64748B] uppercase font-bold">Corroborated Items</span>
            <div className="text-xs font-mono font-semibold text-emerald-400">{findings.length} Verified</div>
          </div>
          <div className="bg-[#0E1624] p-3 rounded-lg border border-[#26364B]">
            <span className="text-[10px] text-[#64748B] uppercase font-bold">Graph Relational Edges</span>
            <div className="text-xs font-mono font-semibold text-sky-400">{graph.edges.length} Connections</div>
          </div>
        </div>
      </div>

      {/* Corroborated Evidence Table */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <h2 className="text-sm font-bold uppercase tracking-wider text-[#F8FAFC]">
          Evidence & Findings Catalogue ({findings.length})
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-[#26364B] text-[#94A3B8] uppercase text-[10px]">
                <th className="py-2.5 px-3">Entity Type</th>
                <th className="py-2.5 px-3">Value</th>
                <th className="py-2.5 px-3">Source Engine</th>
                <th className="py-2.5 px-3">Confidence</th>
                <th className="py-2.5 px-3">Evidence Description</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#26364B]/40">
              {findings.map((f) => (
                <tr key={f.id} className="hover:bg-[#0E1624]/60 transition-colors">
                  <td className="py-2.5 px-3 font-mono text-sky-400 font-bold">{f.entity_type}</td>
                  <td className="py-2.5 px-3 font-mono text-[#F8FAFC] max-w-xs truncate">{f.entity_value}</td>
                  <td className="py-2.5 px-3 text-[#94A3B8]">{f.source_name}</td>
                  <td className="py-2.5 px-3">
                    <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                      {f.confidence}
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-[#CBD5E1] max-w-md truncate">{f.evidence_description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

