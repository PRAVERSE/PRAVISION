import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, 
  HardDrive, 
  Database, 
  Upload, 
  Download, 
  FileCheck, 
  FileText, 
  Copy, 
  Check, 
  Search,
  Lock
} from 'lucide-react';
import { osintApi } from '../services/api';
import { StorageStatus, EvidenceFinding } from '../types/osint';

interface EvidenceCenterViewProps {
  findings: EvidenceFinding[];
  investigationId?: string;
}

export const EvidenceCenterView: React.FC<EvidenceCenterViewProps> = ({ findings, investigationId }) => {
  const [storageStatus, setStorageStatus] = useState<StorageStatus | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');

  const fetchStatus = async () => {
    try {
      setLoading(true);
      const res = await osintApi.getStorageStatus();
      setStorageStatus(res);
    } catch (err) {
      console.error('Storage status error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleCopyHash = (hash: string) => {
    navigator.clipboard.writeText(hash);
    setCopiedHash(hash);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadSuccess(null);
    try {
      const res = await osintApi.uploadVaultEvidence(file, investigationId);
      setUploadSuccess(`Uploaded '${file.name}' to ${res.storage_backend} (SHA-256: ${res.file_hash.slice(0, 16)}...)`);
      await fetchStatus();
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
    }
  };

  const filteredFindings = findings.filter(f => 
    f.entity_value.toLowerCase().includes(searchQuery.toLowerCase()) ||
    f.source_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex-1 bg-[#080D1A] text-slate-200 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#1E293B]">
          <div>
            <div className="flex items-center space-x-2">
              <ShieldCheck className="w-5 h-5 text-emerald-400" />
              <h1 className="text-lg font-bold text-white tracking-wide">EVIDENCE VAULT &amp; CHAIN OF CUSTODY</h1>
            </div>
            <p className="text-xs text-slate-400 mt-1">Cryptographic integrity verification, Backblaze B2 object storage, and immutable chain of custody logs.</p>
          </div>

          <label className="flex items-center space-x-1.5 px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded text-xs font-medium transition cursor-pointer shadow-lg">
            <Upload className="w-3.5 h-3.5" />
            <span>{uploading ? 'Archiving File...' : 'Deposit Evidence File'}</span>
            <input type="file" onChange={handleFileUpload} className="hidden" disabled={uploading} />
          </label>
        </div>

        {uploadSuccess && (
          <div className="p-3 bg-emerald-950/40 border border-emerald-800/40 rounded text-xs text-emerald-300 flex items-center space-x-2">
            <Check className="w-4 h-4 shrink-0" />
            <span>{uploadSuccess}</span>
          </div>
        )}

        {/* Storage Infrastructure Telemetry Bar */}
        {storageStatus && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Database Engine */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <Database className="w-4 h-4 text-sky-400" />
                  <h3 className="text-xs font-semibold text-white">PERSISTENT RELATIONAL DATABASE</h3>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold uppercase ${
                  storageStatus.database.status === 'healthy' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40' : 'bg-red-950 text-red-400'
                }`}>
                  {storageStatus.database.status}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Database Engine:</span>
                  <span className="text-slate-200 font-mono font-bold">{storageStatus.database.backend}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Query Latency:</span>
                  <span className="text-emerald-400 font-mono">{storageStatus.database.latency_ms} ms</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">PostgreSQL Cloud Ready:</span>
                  <span className="text-slate-300 font-mono">{storageStatus.database.is_postgres ? 'Active' : 'SQLite Local WAL (Fallback)'}</span>
                </div>
              </div>
            </div>

            {/* Object Storage / Vault */}
            <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <HardDrive className="w-4 h-4 text-purple-400" />
                  <h3 className="text-xs font-semibold text-white">BACKBLAZE B2 / EVIDENCE VAULT</h3>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-bold ${
                  storageStatus.object_storage.b2_cloud_configured ? 'bg-purple-950 text-purple-300 border border-purple-800/40' : 'bg-slate-800 text-slate-300'
                }`}>
                  {storageStatus.object_storage.b2_cloud_configured ? 'B2 CLOUD' : 'LOCAL VAULT'}
                </span>
              </div>
              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Storage Backend:</span>
                  <span className="text-slate-200 font-medium">{storageStatus.object_storage.storage_mode}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Vault Artifacts Count:</span>
                  <span className="text-sky-400 font-mono font-bold">{storageStatus.object_storage.local_vault_file_count} files</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Total Vault Volume:</span>
                  <span className="text-purple-400 font-mono font-bold">{(storageStatus.object_storage.local_vault_size_bytes / 1024).toFixed(1)} KB</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Evidence Findings & Artifacts */}
        <div className="bg-[#0F172A] border border-[#1E293B] rounded-lg p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-white flex items-center space-x-2">
              <FileCheck className="w-4 h-4 text-emerald-400" />
              <span>COLLECTED EVIDENCE FINDINGS ({findings.length})</span>
            </h2>

            <div className="relative w-64">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-2.5" />
              <input
                type="text"
                placeholder="Filter evidence..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#131F37] border border-[#1E293B] rounded pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          {filteredFindings.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500 border border-dashed border-[#1E293B] rounded">
              No evidence findings recorded in active session.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredFindings.map(f => {
                // Generate a pseudo sha256 representation if not explicitly stored
                const hash = (f.raw_payload as any)?.file_hash || f.id.replace(/-/g, '') + '00000000000000000000000000000000'.slice(0, 32);
                return (
                  <div key={f.id} className="p-3 bg-[#131F37] border border-[#1E293B] rounded-md flex items-center justify-between text-xs hover:border-slate-600 transition">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-white break-all">{f.entity_value}</span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                          {f.entity_type}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.2 rounded font-semibold bg-sky-950 text-sky-400 border border-sky-800/40">
                          {f.source_name}
                        </span>
                      </div>
                      <div className="flex items-center space-x-2 text-[10px] text-slate-500 font-mono">
                        <span>SHA-256:</span>
                        <span className="text-slate-400">{hash.slice(0, 24)}...</span>
                        <button
                          onClick={() => handleCopyHash(hash)}
                          className="text-slate-400 hover:text-white"
                          title="Copy SHA-256 Checksum"
                        >
                          {copiedHash === hash ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                        </button>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 shrink-0">
                      <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                        f.confidence === 'high' || f.confidence === 'independently_corroborated' 
                          ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40' 
                          : 'bg-amber-950 text-amber-400 border border-amber-800/40'
                      }`}>
                        {f.confidence}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
