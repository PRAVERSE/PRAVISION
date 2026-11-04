import React, { useState, useEffect, useRef, Suspense, useCallback } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { CommandCenterView } from './views/CommandCenterView';
import { ViewLoadingFallback } from './components/ViewLoadingFallback';
import { lazyWithRetry } from './utils/lazyWithRetry';

import { osintApi, authApi, getAuthToken, API_BASE } from './services/api';
import { ActiveInvestigation, EvidenceFinding, IntelligenceGraph, ConnectorManifest, UserProfile } from './types/osint';
import { LoginModal } from './components/LoginModal';
import { EntityDossierDrawer } from './components/EntityDossierDrawer';

// Lazy-loaded secondary analytical views (Code-split chunks)
const CasesView = lazyWithRetry(() => import('./views/CasesView'), 'CasesView');
const TimelineView = lazyWithRetry(() => import('./views/TimelineView'), 'TimelineView');
const ThreatIntelView = lazyWithRetry(() => import('./views/ThreatIntelView'), 'ThreatIntelView');
const EntityDatabaseView = lazyWithRetry(() => import('./views/EntityDatabaseView'), 'EntityDatabaseView');
const EvidenceCenterView = lazyWithRetry(() => import('./views/EvidenceCenterView'), 'EvidenceCenterView');
const AiAssistantView = lazyWithRetry(() => import('./views/AiAssistantView'), 'AiAssistantView');
const UniversalSearchView = lazyWithRetry(() => import('./views/UniversalSearchView'), 'UniversalSearchView');
const LiveInvestigationView = lazyWithRetry(() => import('./views/LiveInvestigationView'), 'LiveInvestigationView');
const GothamGraphView = lazyWithRetry(() => import('./views/GothamGraphView'), 'GothamGraphView');
const GlobalMapView = lazyWithRetry(() => import('./views/GlobalMapView'), 'GlobalMapView');
const ImageIntelView = lazyWithRetry(() => import('./views/ImageIntelView'), 'ImageIntelView');
const EmailIntelView = lazyWithRetry(() => import('./views/EmailIntelView'), 'EmailIntelView');
const UsernameIntelView = lazyWithRetry(() => import('./views/UsernameIntelView'), 'UsernameIntelView');
const PhoneIntelView = lazyWithRetry(() => import('./views/PhoneIntelView'), 'PhoneIntelView');
const WebsiteIntelView = lazyWithRetry(() => import('./views/WebsiteIntelView'), 'WebsiteIntelView');
const InfraIntelView = lazyWithRetry(() => import('./views/InfraIntelView'), 'InfraIntelView');
const ToolCenterView = lazyWithRetry(() => import('./views/ToolCenterView'), 'ToolCenterView');
const ReportsView = lazyWithRetry(() => import('./views/ReportsView'), 'ReportsView');
const SettingsView = lazyWithRetry(() => import('./views/SettingsView'), 'SettingsView');

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<string>('overview');
  const [activeInvestigation, setActiveInvestigation] = useState<ActiveInvestigation | null>(null);
  const [findings, setFindings] = useState<EvidenceFinding[]>([]);
  const [graph, setGraph] = useState<IntelligenceGraph>({ nodes: [], edges: [] });
  const [connectors, setConnectors] = useState<ConnectorManifest[]>([]);
  const [settings, setSettings] = useState<any>(null);
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState<boolean>(false);
  const [inspectedEntityId, setInspectedEntityId] = useState<string | null>(null);
  const [wsStatus, setWsStatus] = useState<'connected' | 'connecting' | 'disconnected'>('disconnected');

  const handleSelectEntity = async (entityVal: string) => {
    try {
      const searchRes = await osintApi.searchIntelligence(entityVal);
      const entMatch = (searchRes.results || []).find((r: any) => r.result_type === 'entity');
      if (entMatch) {
        setInspectedEntityId(entMatch.id);
      } else {
        const f = findings.find(x => x.entity_value.toLowerCase() === entityVal.toLowerCase());
        if (f) setInspectedEntityId(f.id);
      }
    } catch (err) {
      console.warn('Entity lookup warning:', err);
    }
  };

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const processedEventIdsRef = useRef<Set<string>>(new Set());

  // Load connectors and settings on mount
  const refreshConnectors = async () => {
    try {
      const manifests = await osintApi.listConnectors();
      setConnectors(manifests);
    } catch (err) {
      console.warn('Connectors fetch error:', err);
    }
  };

  const refreshSettings = async () => {
    try {
      const data = await osintApi.getSettings();
      setSettings(data);
    } catch (err) {
      console.warn('Settings fetch error:', err);
    }
  };

  // Poll/Check active investigation on mount
  const checkActiveInvestigation = async () => {
    try {
      const { active, investigation } = await osintApi.getActiveInvestigation();
      if (active && investigation) {
        setActiveInvestigation(investigation);
        const [res, gr] = await Promise.all([
          osintApi.getInvestigationResults(investigation.id),
          osintApi.getInvestigationGraph(investigation.id)
        ]);
        setFindings(res.findings);
        setGraph(gr);
      }
    } catch (err) {
      console.warn('Active investigation check warning:', err);
    }
  };

  const checkAuth = async () => {
    const token = getAuthToken();
    if (token) {
      try {
        const user = await authApi.getMe();
        setCurrentUser(user);
      } catch (e) {
        setCurrentUser(null);
      }
    }
  };

  useEffect(() => {
    refreshConnectors();
    refreshSettings();
    checkActiveInvestigation();
    checkAuth();
  }, []);

  // Resilient WebSocket connection manager with exponential backoff & tab resume recovery
  const connectWebSocket = useCallback((invId: string) => {
    if (socketRef.current) {
      try {
        socketRef.current.close(1000, "Clean switch");
      } catch (e) {
        // ignore
      }
      socketRef.current = null;
    }

    setWsStatus('connecting');
    let wsUrl: string;
    const wsBase = (import.meta.env.VITE_WS_URL as string) || '';
    if (wsBase) {
      wsUrl = `${wsBase.replace(/^http/, 'ws')}/api/investigations/${invId}/live`;
    } else if (API_BASE.startsWith('http://') || API_BASE.startsWith('https://')) {
      const derivedWs = API_BASE.replace(/^http/, 'ws').replace(/\/api\/?$/, '');
      wsUrl = `${derivedWs}/api/investigations/${invId}/live`;
    } else {
      wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/investigations/${invId}/live`;
    }

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      setWsStatus('connected');
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        const eventKey = `${msg.type}_${msg.connector || ''}_${msg.progress || ''}_${msg.findings_count || ''}`;
        if (processedEventIdsRef.current.has(eventKey)) {
          return; // Deduplicate repeat events
        }
        processedEventIdsRef.current.add(eventKey);
        if (processedEventIdsRef.current.size > 200) {
          processedEventIdsRef.current.clear();
        }

        if (msg.type === 'findings_updated' || msg.type === 'connector_completed') {
          const [res, gr, invStatus] = await Promise.all([
            osintApi.getInvestigationResults(invId),
            osintApi.getInvestigationGraph(invId),
            osintApi.getActiveInvestigation()
          ]);
          setFindings(res.findings);
          setGraph(gr);
          if (invStatus.investigation) {
            setActiveInvestigation(invStatus.investigation);
          }
        } else if (msg.type === 'investigation_finished') {
          const invStatus = await osintApi.getActiveInvestigation();
          if (invStatus.investigation) {
            setActiveInvestigation(invStatus.investigation);
          }
        }
      } catch (err) {
        console.error('WS parse error:', err);
      }
    };

    ws.onerror = (err) => {
      console.warn('WS communication error:', err);
    };

    ws.onclose = (event) => {
      setWsStatus('disconnected');
      socketRef.current = null;

      // Only attempt reconnection if closure was abnormal and investigation is still running
      if (event.code !== 1000 && activeInvestigation?.status === 'running') {
        const maxAttempts = 5;
        if (reconnectAttemptsRef.current < maxAttempts) {
          const backoffDelay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 16000);
          reconnectAttemptsRef.current += 1;
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWebSocket(invId);
          }, backoffDelay);
        }
      }
    };
  }, [activeInvestigation?.status]);

  useEffect(() => {
    if (!activeInvestigation || activeInvestigation.status !== 'running') {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close(1000, "Normal termination");
        socketRef.current = null;
      }
      setWsStatus('disconnected');
      return;
    }

    connectWebSocket(activeInvestigation.id);

    // Browser tab visibility change listener
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible' && (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN)) {
        if (activeInvestigation?.status === 'running') {
          connectWebSocket(activeInvestigation.id);
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close(1000, "Unmount");
        socketRef.current = null;
      }
    };
  }, [activeInvestigation?.id, activeInvestigation?.status, connectWebSocket]);

  const handleStartInvestigation = async (target: string, mode?: string, depth?: number) => {
    try {
      const newInv = await osintApi.startInvestigation(target, mode, depth);
      setActiveInvestigation(newInv);
      setFindings([]);
      setGraph({ nodes: [], edges: [] });
      setCurrentView('live');
    } catch (err) {
      alert('Failed to launch investigation: ' + err);
    }
  };

  const handleClearInvestigation = async () => {
    if (activeInvestigation) {
      await osintApi.clearInvestigation(activeInvestigation.id);
    }
    setActiveInvestigation(null);
    setFindings([]);
    setGraph({ nodes: [], edges: [] });
    setCurrentView('overview');
  };

  const handleCancelInvestigation = async () => {
    if (activeInvestigation) {
      await osintApi.cancelInvestigation(activeInvestigation.id);
      const invStatus = await osintApi.getActiveInvestigation();
      if (invStatus.investigation) {
        setActiveInvestigation(invStatus.investigation);
      }
    }
  };

  const operationalCount = connectors.filter(c => c.health === 'operational').length;

  return (
    <div className="min-h-screen bg-[#080D16] text-[#F8FAFC] flex flex-col font-sans">
      <Header
        investigation={activeInvestigation}
        onClear={handleClearInvestigation}
        onNavigate={setCurrentView}
        operationalConnectorsCount={operationalCount}
        currentUser={currentUser}
        onOpenLogin={() => setIsLoginModalOpen(true)}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentView={currentView}
          onNavigate={setCurrentView}
          hasActiveInvestigation={Boolean(activeInvestigation)}
          userRole={currentUser?.role}
        />

        <main className="flex-1 overflow-y-auto bg-[#080D16]">
          {(currentView === 'overview' || currentView === 'command_center') && (
            <CommandCenterView
              activeInvestigation={activeInvestigation}
              findings={findings}
              graph={graph}
              onNavigate={setCurrentView}
            />
          )}

          <Suspense fallback={<ViewLoadingFallback title={`LOADING ${currentView.toUpperCase().replace('_', ' ')}`} />}>
            {currentView === 'cases' && (
              <CasesView
                activeInvestigation={activeInvestigation}
              />
            )}

            {currentView === 'timeline' && (
              <TimelineView />
            )}

            {currentView === 'threat_intel' && (
              <ThreatIntelView />
            )}

            {currentView === 'entity_db' && (
              <EntityDatabaseView
                findings={findings}
                onSelectEntity={handleSelectEntity}
              />
            )}

            {currentView === 'evidence_vault' && (
              <EvidenceCenterView
                findings={findings}
                investigationId={activeInvestigation?.id}
              />
            )}

            {currentView === 'ai_assistant' && (
              <AiAssistantView />
            )}

            {currentView === 'search' && (
              <UniversalSearchView
                onStartInvestigation={handleStartInvestigation}
                onNavigate={setCurrentView}
                onSelectEntity={handleSelectEntity}
              />
            )}

            {currentView === 'live' && (
              <LiveInvestigationView
                investigation={activeInvestigation}
                findings={findings}
                onCancel={handleCancelInvestigation}
                onNavigate={setCurrentView}
              />
            )}

            {currentView === 'graph' && (
              <GothamGraphView
                graph={graph}
                findings={findings}
                onSelectEntity={handleSelectEntity}
              />
            )}

            {currentView === 'map' && (
              <GlobalMapView findings={findings} />
            )}

            {currentView === 'image_intel' && (
              <ImageIntelView />
            )}

            {currentView === 'email_intel' && (
              <EmailIntelView
                onStartInvestigation={handleStartInvestigation}
                findings={findings}
              />
            )}

            {currentView === 'username_intel' && (
              <UsernameIntelView
                onStartInvestigation={handleStartInvestigation}
                findings={findings}
              />
            )}

            {currentView === 'phone_intel' && (
              <PhoneIntelView
                onStartInvestigation={handleStartInvestigation}
                findings={findings}
              />
            )}

            {currentView === 'website_intel' && (
              <WebsiteIntelView
                onStartInvestigation={handleStartInvestigation}
                findings={findings}
              />
            )}

            {currentView === 'infra_intel' && (
              <InfraIntelView
                onStartInvestigation={handleStartInvestigation}
                findings={findings}
              />
            )}

            {currentView === 'tool_center' && (
              <ToolCenterView
                connectors={connectors}
                onRefresh={refreshConnectors}
              />
            )}

            {currentView === 'reports' && (
              <ReportsView
                investigation={activeInvestigation}
                findings={findings}
                graph={graph}
              />
            )}

            {currentView === 'settings' && (
              <SettingsView
                settings={settings}
                onRefreshSettings={refreshSettings}
              />
            )}
          </Suspense>
        </main>
      </div>

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        currentUser={currentUser}
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          refreshConnectors();
        }}
        onLogoutSuccess={() => {
          setCurrentUser(null);
        }}
      />

      <EntityDossierDrawer
        entityId={inspectedEntityId}
        onClose={() => setInspectedEntityId(null)}
        onFocusInGraph={() => {
          setCurrentView('graph');
          setInspectedEntityId(null);
        }}
      />
    </div>
  );
};

export default App;
