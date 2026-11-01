import React, { useState } from 'react';
import { 
  Settings, 
  Key, 
  ShieldCheck, 
  Sliders, 
  Trash2, 
  Save, 
  CheckCircle2, 
  AlertCircle 
} from 'lucide-react';
import { osintApi } from '../services/api';

interface SettingsViewProps {
  settings: any;
  onRefreshSettings: () => void;
}

export const SettingsView: React.FC<SettingsViewProps> = ({ settings, onRefreshSettings }) => {
  const [maxDepth, setMaxDepth] = useState(settings?.limits?.max_depth || 2);
  const [maxEntities, setMaxEntities] = useState(settings?.limits?.max_discovered_entities || 150);
  const [timeoutSec, setTimeoutSec] = useState(settings?.limits?.connector_timeout_seconds || 35);

  const [shodanKey, setShodanKey] = useState('');
  const [hibpKey, setHibpKey] = useState('');
  const [hunterKey, setHunterKey] = useState('');
  const [censysId, setCensysId] = useState('');
  const [censysSecret, setCensysSecret] = useState('');
  const [intelxKey, setIntelxKey] = useState('');

  const [savedSuccess, setSavedSuccess] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      const payload: any = {
        limits: {
          max_depth: maxDepth,
          max_discovered_entities: maxEntities,
          connector_timeout_seconds: timeoutSec
        },
        api_keys: {}
      };
      if (shodanKey) payload.api_keys.shodan_api_key = shodanKey;
      if (hibpKey) payload.api_keys.hibp_api_key = hibpKey;
      if (hunterKey) payload.api_keys.hunter_api_key = hunterKey;
      if (censysId) payload.api_keys.censys_api_id = censysId;
      if (censysSecret) payload.api_keys.censys_api_secret = censysSecret;
      if (intelxKey) payload.api_keys.intelx_api_key = intelxKey;

      await osintApi.updateSettings(payload);
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
      onRefreshSettings();
    } catch (err) {
      alert('Save failed: ' + err);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePurge = async () => {
    if (confirm('Are you sure you want to securely purge all ephemeral files and wipe memory buffers?')) {
      const res = await osintApi.purgeAllData();
      alert(`Purge complete. ${res.items_removed} ephemeral files deleted.`);
      onRefreshSettings();
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-6">
      <div className="border-b border-[#26364B] pb-4">
        <h1 className="text-2xl font-extrabold text-[#F8FAFC]">Platform Settings & Privacy Control</h1>
        <p className="text-xs text-[#94A3B8]">
          Investigation recursion bounds, API credential vault, and ephemeral scratch file sanitization.
        </p>
      </div>

      {savedSuccess && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>Settings and in-memory credentials updated successfully.</span>
        </div>
      )}

      {/* Investigation Bounds */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#26364B] pb-2 text-sm font-bold text-[#F8FAFC]">
          <Sliders className="w-4 h-4 text-sky-400" />
          <span>Recursive Investigation Bounds</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="space-y-1">
            <span className="text-[#94A3B8]">Max Recursive Depth (1-5):</span>
            <input
              type="number"
              min="1"
              max="5"
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <span className="text-[#94A3B8]">Max Discovered Entities:</span>
            <input
              type="number"
              min="10"
              max="500"
              value={maxEntities}
              onChange={(e) => setMaxEntities(Number(e.target.value))}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <span className="text-[#94A3B8]">Connector Timeout (sec):</span>
            <input
              type="number"
              min="5"
              max="120"
              value={timeoutSec}
              onChange={(e) => setTimeoutSec(Number(e.target.value))}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* API Key Vault */}
      <div className="bg-[#121D2D] border border-[#26364B] rounded-2xl p-6 space-y-4">
        <div className="flex items-center space-x-2 border-b border-[#26364B] pb-2 text-sm font-bold text-[#F8FAFC]">
          <Key className="w-4 h-4 text-amber-400" />
          <span>Optional Commercial API Key Vault</span>
        </div>
        <p className="text-xs text-[#94A3B8]">
          Keys are stored in memory or user-protected credentials only. They are never written to unencrypted configuration or exposed to client JavaScript.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[#94A3B8]">Shodan API Key:</span>
              <span className="text-[10px] font-mono text-emerald-400">
                {settings?.configured_api_keys?.shodan_api_key ? '● Configured' : '○ Not Set'}
              </span>
            </div>
            <input
              type="password"
              placeholder="Paste new Shodan API Key..."
              value={shodanKey}
              onChange={(e) => setShodanKey(e.target.value)}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[#94A3B8]">Have I Been Pwned Key:</span>
              <span className="text-[10px] font-mono text-emerald-400">
                {settings?.configured_api_keys?.hibp_api_key ? '● Configured' : '○ Not Set'}
              </span>
            </div>
            <input
              type="password"
              placeholder="Paste new HIBP API Key..."
              value={hibpKey}
              onChange={(e) => setHibpKey(e.target.value)}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[#94A3B8]">Hunter.io API Key:</span>
              <span className="text-[10px] font-mono text-emerald-400">
                {settings?.configured_api_keys?.hunter_api_key ? '● Configured' : '○ Not Set'}
              </span>
            </div>
            <input
              type="password"
              placeholder="Paste new Hunter API Key..."
              value={hunterKey}
              onChange={(e) => setHunterKey(e.target.value)}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>

          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[#94A3B8]">Intelligence X API Key:</span>
              <span className="text-[10px] font-mono text-emerald-400">
                {settings?.configured_api_keys?.intelx_api_key ? '● Configured' : '○ Not Set'}
              </span>
            </div>
            <input
              type="password"
              placeholder="Paste new IntelX API Key..."
              value={intelxKey}
              onChange={(e) => setIntelxKey(e.target.value)}
              className="w-full bg-[#080D16] border border-[#26364B] rounded-lg px-3 py-2 text-[#F8FAFC] font-mono focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* Save Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="flex items-center space-x-2 px-6 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 text-white font-bold text-xs cursor-pointer shadow-lg shadow-sky-500/20 transition-all"
        >
          <Save className="w-4 h-4" />
          <span>Save Platform Settings</span>
        </button>
      </div>

      {/* Zero History Policy & Purge */}
      <div className="bg-[#121D2D] border border-red-500/30 rounded-2xl p-6 space-y-4">
        <div className="flex items-center space-x-2 text-sm font-bold text-red-400">
          <Trash2 className="w-4 h-4" />
          <span>Strict Zero-History & Ephemeral Storage Sanitizer</span>
        </div>
        <p className="text-xs text-[#CBD5E1] leading-relaxed">
          PRAVISION does not maintain persistent investigation histories or saved profiles. All uploaded media, 
          temporary ELA difference maps, and volatile memory graphs are completely wiped when an investigation is cleared or when you click purge.
        </p>

        <button
          onClick={handlePurge}
          className="px-4 py-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 text-xs font-semibold cursor-pointer transition-all"
        >
          Purge Ephemeral Runtime Buffers Now
        </button>
      </div>
    </div>
  );
};
