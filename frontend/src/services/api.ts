import { ClassifiedInput, ActiveInvestigation, EvidenceFinding, IntelligenceGraph, ConnectorManifest } from '../types/osint';

const API_BASE = '/api';

export const osintApi = {
  async classify(input: string): Promise<ClassifiedInput> {
    const res = await fetch(`${API_BASE}/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async startInvestigation(target: string, mode?: string, depth: number = 2): Promise<ActiveInvestigation> {
    const res = await fetch(`${API_BASE}/investigations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, mode, depth })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getActiveInvestigation(): Promise<{ active: boolean; investigation: ActiveInvestigation | null }> {
    const res = await fetch(`${API_BASE}/investigations/active`);
    if (!res.ok) return { active: false, investigation: null };
    return res.json();
  },

  async getInvestigationResults(id: string): Promise<{ total_findings: number; findings: EvidenceFinding[] }> {
    const res = await fetch(`${API_BASE}/investigations/${id}/results`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getInvestigationGraph(id: string): Promise<IntelligenceGraph> {
    const res = await fetch(`${API_BASE}/investigations/${id}/graph`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async clearInvestigation(id: string): Promise<void> {
    await fetch(`${API_BASE}/investigations/${id}`, { method: 'DELETE' });
  },

  async cancelInvestigation(id: string): Promise<void> {
    await fetch(`${API_BASE}/investigations/${id}/cancel`, { method: 'POST' });
  },

  async listConnectors(): Promise<ConnectorManifest[]> {
    const res = await fetch(`${API_BASE}/connectors`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async testConnector(name: string): Promise<{ health: string; manifest: ConnectorManifest }> {
    const res = await fetch(`${API_BASE}/connectors/${name}/health-check`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async toggleConnector(name: string, enabled: boolean): Promise<any> {
    const res = await fetch(`${API_BASE}/connectors/${name}/toggle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async uploadMedia(file: File): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async exportReport(format: 'html' | 'pdf' | 'json'): Promise<Blob> {
    const res = await fetch(`${API_BASE}/reports/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.blob();
  },

  async getSettings(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async updateSettings(payload: any): Promise<any> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async purgeAllData(): Promise<any> {
    const res = await fetch(`${API_BASE}/settings/purge`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
};
