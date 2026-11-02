import React, { useState } from 'react';
import { 
  Upload, 
  Image as ImageIcon, 
  Camera, 
  Clock, 
  MapPin, 
  Hash, 
  Search, 
  ShieldCheck, 
  AlertTriangle, 
  ExternalLink 
} from 'lucide-react';
import { osintApi } from '../services/api';

export const ImageIntelView: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [analysisResult, setAnalysisResult] = useState<any | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [activeTab, setActiveTab] = useState<'metadata' | 'forensics' | 'reverse'>('metadata');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setPreviewUrl(URL.createObjectURL(selectedFile));
      setIsUploading(true);

      try {
        const res = await osintApi.uploadMedia(selectedFile);
        setAnalysisResult(res);
      } catch (err) {
        alert('Image processing error: ' + err);
      } finally {
        setIsUploading(false);
      }
    }
  };

  const meta = analysisResult?.metadata;
  const hashes = analysisResult?.hashes;
  const ela = analysisResult?.ela;

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between border-b border-[#26364B] pb-4">
        <div>
          <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Media & Image Intelligence</h1>
          <p className="text-xs text-[#94A3B8]">
            EXIF extraction, GPS geolocation, cryptographic/perceptual hashing, Error Level Analysis (ELA), and reverse visual search.
          </p>
        </div>
      </div>

      {/* Upload Dropzone */}
      {!previewUrl && (
        <label className="border-2 border-dashed border-[#26364B] hover:border-sky-500/50 bg-[#121D2D]/60 rounded-2xl p-12 flex flex-col items-center justify-center space-y-3 cursor-pointer transition-all">
          <div className="w-14 h-14 rounded-full bg-sky-500/10 flex items-center justify-center text-sky-400">
            <Upload className="w-6 h-6" />
          </div>
          <span className="text-sm font-semibold text-[#F8FAFC]">Select or Drag & Drop Image/Document</span>
          <span className="text-xs text-[#64748B]">Supports JPEG, PNG, WEBP, TIFF, PDF, DOCX (Max 25MB)</span>
          <input type="file" onChange={handleFileChange} className="hidden" accept="image/*,.pdf,.docx" />
        </label>
      )}

      {/* Image Intelligence Workspace */}
      {previewUrl && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Preview & Actions */}
          <div className="lg:col-span-5 bg-[#121D2D] border border-[#26364B] rounded-2xl p-5 space-y-4">
            <div className="w-full h-72 rounded-xl bg-[#080D16] border border-[#26364B] flex items-center justify-center overflow-hidden relative">
              <img src={previewUrl} alt="Preview" className="max-h-full max-w-full object-contain" />
              {isUploading && (
                <div className="absolute inset-0 bg-[#080D16]/80 flex items-center justify-center text-xs text-sky-400 font-mono">
                  Analyzing Media Forensics...
                </div>
              )}
            </div>

            <div className="flex items-center justify-between">
              <label className="text-xs text-sky-400 hover:text-sky-300 font-semibold cursor-pointer">
                <span>Upload Another File</span>
                <input type="file" onChange={handleFileChange} className="hidden" accept="image/*,.pdf,.docx" />
              </label>
              <span className="text-xs font-mono text-[#94A3B8]">{file?.name}</span>
            </div>

            {/* Hashes Card */}
            {hashes && (
              <div className="bg-[#0E1624] p-3.5 rounded-xl border border-[#26364B] space-y-2 text-xs font-mono">
                <div className="flex items-center space-x-1.5 text-sky-400 font-sans font-bold text-xs">
                  <Hash className="w-3.5 h-3.5" />
                  <span>Media Signatures</span>
                </div>
                <div className="space-y-1 text-[11px] text-[#CBD5E1]">
                  <div className="truncate"><strong className="text-[#64748B]">SHA-256:</strong> {hashes.sha256}</div>
                  <div className="truncate"><strong className="text-[#64748B]">MD5:</strong> {hashes.md5}</div>
                  <div className="truncate"><strong className="text-[#64748B]">pHash:</strong> {hashes.phash}</div>
                </div>
              </div>
            )}
          </div>

          {/* Right Tabbed Results */}
          <div className="lg:col-span-7 bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-6">
            {/* Tabs */}
            <div className="flex items-center space-x-2 border-b border-[#26364B] pb-3">
              <button
                onClick={() => setActiveTab('metadata')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'metadata' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'text-[#94A3B8] hover:text-[#F8FAFC]'
                }`}
              >
                EXIF Metadata
              </button>
              <button
                onClick={() => setActiveTab('forensics')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'forensics' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'text-[#94A3B8] hover:text-[#F8FAFC]'
                }`}
              >
                Error Level Analysis (ELA)
              </button>
              <button
                onClick={() => setActiveTab('reverse')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                  activeTab === 'reverse' ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30' : 'text-[#94A3B8] hover:text-[#F8FAFC]'
                }`}
              >
                Reverse Visual Queries
              </button>
            </div>

            {/* Tab 1: Metadata */}
            {activeTab === 'metadata' && (
              <div className="space-y-4 text-xs">
                {meta?.has_exif ? (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="bg-[#0E1624] p-3.5 rounded-xl border border-[#26364B] space-y-1">
                      <span className="text-[#64748B] text-[10px] uppercase font-bold">Camera Equipment</span>
                      <div className="text-sm font-bold text-[#F8FAFC]">
                        {meta.camera_make || 'Unknown Make'} {meta.camera_model || ''}
                      </div>
                      <div className="text-[#94A3B8] text-[11px]">Software: {meta.software || 'Firmware Default'}</div>
                    </div>

                    <div className="bg-[#0E1624] p-3.5 rounded-xl border border-[#26364B] space-y-1">
                      <span className="text-[#64748B] text-[10px] uppercase font-bold">Original Timestamp</span>
                      <div className="text-sm font-bold text-[#F8FAFC]">
                        {meta.datetime_original || 'No EXIF Timestamp'}
                      </div>
                      <div className="text-[#94A3B8] text-[11px]">Dimensions: {meta.dimensions}</div>
                    </div>

                    {meta.gps_coordinates && (
                      <div className="col-span-2 bg-[#0E1624] p-4 rounded-xl border border-sky-500/30 space-y-2">
                        <div className="flex items-center space-x-1.5 text-sky-400 font-bold">
                          <MapPin className="w-4 h-4" />
                          <span>Embedded GPS Geotag Found</span>
                        </div>
                        <div className="text-base font-mono font-bold text-[#F8FAFC]">
                          Latitude: {meta.gps_coordinates[0]}, Longitude: {meta.gps_coordinates[1]}
                        </div>
                        <a
                          href={`https://www.google.com/maps?q=${meta.gps_coordinates[0]},${meta.gps_coordinates[1]}`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 text-xs text-sky-400 hover:underline pt-1"
                        >
                          <span>Open in Google Maps</span>
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="py-8 text-center text-[#94A3B8]">
                    No standard EXIF header metadata embedded in this file. Hashes and dimensions remain available.
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Forensics ELA */}
            {activeTab === 'forensics' && (
              <div className="space-y-4">
                <div className="flex items-center space-x-2 text-xs text-[#CBD5E1]">
                  <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                  <span>Error Level Analysis highlights compression discrepancy levels to spot digital splices.</span>
                </div>

                {ela?.ela_image_filename ? (
                  <div className="space-y-3">
                    <div className="w-full h-64 rounded-xl bg-[#080D16] border border-[#26364B] flex items-center justify-center overflow-hidden">
                      <img 
                        src={`/temp-media/${ela.ela_image_filename}`} 
                        alt="ELA Output" 
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>
                    <div className="p-3 bg-[#0E1624] rounded-lg border border-[#26364B] text-xs text-[#CBD5E1]">
                      <strong>Forensic Notes:</strong> {ela.forensic_notes}
                    </div>
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-[#64748B]">Upload an image to render real-time ELA difference analysis.</div>
                )}
              </div>
            )}

            {/* Tab 3: Reverse Visual Queries */}
            {activeTab === 'reverse' && (
              <div className="space-y-3 text-xs">
                <p className="text-[#94A3B8]">
                  Authorized non-biometric visual search links across major search engines for landmark, duplicate, and origin website discovery:
                </p>

                <div className="space-y-2">
                  <a
                    href="https://lens.google.com"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3 rounded-xl bg-[#0E1624] hover:bg-[#1E293B] border border-[#26364B] transition-all text-[#F8FAFC]"
                  >
                    <span>Google Lens Visual Search</span>
                    <ExternalLink className="w-4 h-4 text-sky-400" />
                  </a>
                  <a
                    href="https://tineye.com"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3 rounded-xl bg-[#0E1624] hover:bg-[#1E293B] border border-[#26364B] transition-all text-[#F8FAFC]"
                  >
                    <span>TinEye Reverse Image Search</span>
                    <ExternalLink className="w-4 h-4 text-sky-400" />
                  </a>
                  <a
                    href="https://yandex.com/images"
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center justify-between p-3 rounded-xl bg-[#0E1624] hover:bg-[#1E293B] border border-[#26364B] transition-all text-[#F8FAFC]"
                  >
                    <span>Yandex Visual Landmark Search</span>
                    <ExternalLink className="w-4 h-4 text-sky-400" />
                  </a>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

