import {
  ClassifiedInput,
  ActiveInvestigation,
  EvidenceFinding,
  IntelligenceGraph,
  ConnectorManifest,
  CaseDossier,
  StorageStatus,
  GraphAnalyticsResult,
  TimelineResult,
  ThreatPostureResult,
  AiBriefingResult
} from '../types/osint';

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
  },

  // Case Dossiers (Stage 5)
  async listCases(): Promise<CaseDossier[]> {
    const res = await fetch(`${API_BASE}/cases`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async createCase(payload: { title: string; description?: string; classification?: string; tags?: string[] }): Promise<CaseDossier> {
    const res = await fetch(`${API_BASE}/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getCase(caseId: string): Promise<CaseDossier> {
    const res = await fetch(`${API_BASE}/cases/${caseId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async deleteCase(caseId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/cases/${caseId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async saveActiveToCase(caseId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/cases/${caseId}/save-active`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Storage & Vault (Stage 5)
  async getStorageStatus(): Promise<StorageStatus> {
    const res = await fetch(`${API_BASE}/storage/status`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async uploadVaultEvidence(file: File, investigationId?: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (investigationId) formData.append('investigation_id', investigationId);
    const res = await fetch(`${API_BASE}/storage/evidence/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Intelligence Engine (Stage 6)
  async getEntityResolution(): Promise<any> {
    const res = await fetch(`${API_BASE}/intelligence/entity-resolution`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getGraphAnalytics(): Promise<GraphAnalyticsResult> {
    const res = await fetch(`${API_BASE}/intelligence/graph-analytics`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getShortestPath(source: string, target: string): Promise<{ found: boolean; path: string[] }> {
    const res = await fetch(`${API_BASE}/intelligence/shortest-path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getTimeline(): Promise<TimelineResult> {
    const res = await fetch(`${API_BASE}/intelligence/timeline`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getThreatPosture(): Promise<ThreatPostureResult> {
    const res = await fetch(`${API_BASE}/intelligence/threat-posture`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async scanDocumentText(text: string): Promise<any> {
    const res = await fetch(`${API_BASE}/intelligence/document/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getAiBriefing(): Promise<AiBriefingResult> {
    const res = await fetch(`${API_BASE}/intelligence/briefing`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async askAiAssistant(query: string): Promise<any> {
    const res = await fetch(`${API_BASE}/intelligence/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
};

