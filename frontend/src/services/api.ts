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
  AiBriefingResult,
  UserProfile,
  UserRole
} from '../types/osint';

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string) || '/api';

let onUnauthorizedCallback: (() => void) | null = null;

export function setOnUnauthorizedCallback(cb: (() => void) | null) {
  onUnauthorizedCallback = cb;
}

export function getAuthToken(): string | null {
  return localStorage.getItem('pravision_token');
}

export function setAuthToken(token: string | null) {
  if (token) {
    localStorage.setItem('pravision_token', token);
  } else {
    localStorage.removeItem('pravision_token');
  }
}

export async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = getAuthToken();
  const headers = new Headers(init?.headers || {});
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const res = await fetch(url, { ...init, headers, credentials: 'include' });
  if (res.status === 401 && !url.includes('/auth/login') && !url.includes('/auth/session')) {
    if (onUnauthorizedCallback) {
      onUnauthorizedCallback();
    }
  }
  return res;
}

export const authApi = {
  async login(username: string, password: string): Promise<{ access_token: string; refresh_token: string; token_type: string; expires_in: number; user: UserProfile }> {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      credentials: 'include'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || 'Authentication failed. Please verify credentials.');
    }
    const data = await res.json();
    setAuthToken(data.access_token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      const token = getAuthToken();
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        credentials: 'include'
      });
    } catch (e) {
      // ignore
    } finally {
      setAuthToken(null);
    }
  },

  async getSession(): Promise<{ authenticated: boolean; user: UserProfile | null }> {
    try {
      const token = getAuthToken();
      const headers = new Headers();
      if (token) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      const res = await fetch(`${API_BASE}/auth/session`, {
        headers,
        credentials: 'include'
      });
      if (res.ok) {
        return await res.json();
      }
    } catch (e) {
      // ignore
    }
    return { authenticated: false, user: null };
  },

  async getMe(): Promise<UserProfile> {
    const res = await authFetch(`${API_BASE}/auth/me`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listUsers(): Promise<UserProfile[]> {
    const res = await authFetch(`${API_BASE}/auth/users`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async updateUserStatus(userId: string, isActive: boolean): Promise<any> {
    const res = await authFetch(`${API_BASE}/auth/users/${userId}/status`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_active: isActive })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async updateUserRole(userId: string, role: UserRole): Promise<any> {
    const res = await authFetch(`${API_BASE}/auth/users/${userId}/role`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ role })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async shareCase(caseId: string, targetUserId: string, permission: 'read' | 'write' | 'admin' = 'read'): Promise<any> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/share`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_user_id: targetUserId, permission })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async revokeCaseShare(caseId: string, targetUserId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/share/${targetUserId}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async listCaseMembers(caseId: string): Promise<any[]> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/members`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
};

export const osintApi = {
  async classify(input: string): Promise<ClassifiedInput> {
    const res = await authFetch(`${API_BASE}/classify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ input })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async startInvestigation(target: string, mode?: string, depth: number = 2): Promise<ActiveInvestigation> {
    const res = await authFetch(`${API_BASE}/investigations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target, mode, depth })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getActiveInvestigation(): Promise<{ active: boolean; investigation: ActiveInvestigation | null }> {
    const res = await authFetch(`${API_BASE}/investigations/active`);
    if (!res.ok) return { active: false, investigation: null };
    return res.json();
  },

  async getInvestigationResults(id: string): Promise<{ total_findings: number; findings: EvidenceFinding[] }> {
    const res = await authFetch(`${API_BASE}/investigations/${id}/results`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getInvestigationGraph(id: string): Promise<IntelligenceGraph> {
    const res = await authFetch(`${API_BASE}/investigations/${id}/graph`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async clearInvestigation(id: string): Promise<void> {
    await authFetch(`${API_BASE}/investigations/${id}`, { method: 'DELETE' });
  },

  async cancelInvestigation(id: string): Promise<void> {
    await authFetch(`${API_BASE}/investigations/${id}/cancel`, { method: 'POST' });
  },

  async listConnectors(): Promise<ConnectorManifest[]> {
    const res = await authFetch(`${API_BASE}/connectors`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async testConnector(name: string): Promise<{ health: string; manifest: ConnectorManifest }> {
    const res = await authFetch(`${API_BASE}/connectors/${name}/health-check`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async toggleConnector(name: string, enabled: boolean): Promise<any> {
    const res = await authFetch(`${API_BASE}/connectors/${name}/toggle`, {
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
    const res = await authFetch(`${API_BASE}/media/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async exportReport(format: 'html' | 'pdf' | 'json'): Promise<Blob> {
    const res = await authFetch(`${API_BASE}/reports/export`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ format })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.blob();
  },

  async getSettings(): Promise<any> {
    const res = await authFetch(`${API_BASE}/settings`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async updateSettings(payload: any): Promise<any> {
    const res = await authFetch(`${API_BASE}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async purgeAllData(): Promise<any> {
    const res = await authFetch(`${API_BASE}/settings/purge`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Case Dossiers (Stage 5)
  async listCases(): Promise<CaseDossier[]> {
    const res = await authFetch(`${API_BASE}/cases`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async createCase(payload: { title: string; description?: string; classification?: string; tags?: string[] }): Promise<CaseDossier> {
    const res = await authFetch(`${API_BASE}/cases`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getCase(caseId: string): Promise<CaseDossier> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async deleteCase(caseId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async saveActiveToCase(caseId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/cases/${caseId}/save-active`, { method: 'POST' });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Storage & Vault (Stage 5)
  async getStorageStatus(): Promise<StorageStatus> {
    const res = await authFetch(`${API_BASE}/storage/status`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async uploadVaultEvidence(file: File, investigationId?: string): Promise<any> {
    const formData = new FormData();
    formData.append('file', file);
    if (investigationId) formData.append('investigation_id', investigationId);
    const res = await authFetch(`${API_BASE}/storage/evidence/upload`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Intelligence Engine (Stage 6)
  async getEntityResolution(): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/entity-resolution`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getGraphAnalytics(): Promise<GraphAnalyticsResult> {
    const res = await authFetch(`${API_BASE}/intelligence/graph-analytics`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getShortestPath(source: string, target: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/shortest-path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  // Gotham-Grade Intelligence Workstation Extensions
  async searchIntelligence(query: string, entityType?: string, caseId?: string, minConfidence?: string): Promise<any> {
    const params = new URLSearchParams({ q: query });
    if (entityType && entityType !== 'all') params.append('entity_type', entityType);
    if (caseId) params.append('case_id', caseId);
    if (minConfidence && minConfidence !== 'all') params.append('min_confidence', minConfidence);
    const res = await authFetch(`${API_BASE}/intelligence/search?${params.toString()}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getCaseMergeCandidates(caseId: string, threshold = 0.70): Promise<any[]> {
    const res = await authFetch(`${API_BASE}/intelligence/cases/${caseId}/merge-candidates?threshold=${threshold}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async mergeEntities(canonicalId: string, absorbedIds: string[], reason?: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/entities/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        canonical_entity_id: canonicalId,
        absorbed_entity_ids: absorbedIds,
        reason: reason || 'Analyst verified identity merge'
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async unmergeEntity(canonicalId: string, absorbedId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/entities/${encodeURIComponent(canonicalId)}/unmerge/${encodeURIComponent(absorbedId)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async expandGraphNeighborhood(seedNodeIds: string[], hops = 1, allowedRelationTypes?: string[], minConfidence?: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/graph/expand`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seed_node_ids: seedNodeIds,
        hops,
        allowed_relation_types: allowedRelationTypes,
        min_confidence: minConfidence
      })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getEntityDossier(entityId: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/entities/${encodeURIComponent(entityId)}/dossier`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getTimeline(): Promise<TimelineResult> {
    const res = await authFetch(`${API_BASE}/intelligence/timeline`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getThreatPosture(): Promise<ThreatPostureResult> {
    const res = await authFetch(`${API_BASE}/intelligence/threat-posture`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async scanDocumentText(text: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/document/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async getAiBriefing(): Promise<AiBriefingResult> {
    const res = await authFetch(`${API_BASE}/intelligence/briefing`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },

  async askAiAssistant(query: string): Promise<any> {
    const res = await authFetch(`${API_BASE}/intelligence/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
};

