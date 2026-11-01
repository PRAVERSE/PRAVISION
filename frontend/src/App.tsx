import React, { useState, useEffect, useRef } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { OverviewView } from './views/OverviewView';
import { UniversalSearchView } from './views/UniversalSearchView';
import { LiveInvestigationView } from './views/LiveInvestigationView';
import { IntelligenceGraphView } from './views/IntelligenceGraphView';
import { GlobalMapView } from './views/GlobalMapView';
import { ImageIntelView } from './views/ImageIntelView';
import { EmailIntelView } from './views/EmailIntelView';
import { UsernameIntelView } from './views/UsernameIntelView';
import { PhoneIntelView } from './views/PhoneIntelView';
import { WebsiteIntelView } from './views/WebsiteIntelView';
import { InfraIntelView } from './views/InfraIntelView';
import { ToolCenterView } from './views/ToolCenterView';
import { ReportsView } from './views/ReportsView';
import { SettingsView } from './views/SettingsView';

import { osintApi } from './services/api';
import { ActiveInvestigation, EvidenceFinding, IntelligenceGraph, ConnectorManifest } from './types/osint';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<string>('overview');
  const [activeInvestigation, setActiveInvestigation] = useState<ActiveInvestigation | null>(null);
  const [findings, setFindings] = useState<EvidenceFinding[]>([]);
  const [graph, setGraph] = useState<IntelligenceGraph>({ nodes: [], edges: [] });
  const [connectors, setConnectors] = useState<ConnectorManifest[]>([]);
  const [settings, setSettings] = useState<any>(null);

  const socketRef = useRef<WebSocket | null>(null);

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

  useEffect(() => {
    refreshConnectors();
    refreshSettings();
    checkActiveInvestigation();
  }, []);

  // WebSocket Live Updates
  useEffect(() => {
    if (!activeInvestigation || activeInvestigation.status !== 'running') {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${proto}//${host}/api/investigations/${activeInvestigation.id}/live`;

    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'findings_updated' || msg.type === 'connector_completed') {
          const [res, gr, invStatus] = await Promise.all([
            osintApi.getInvestigationResults(activeInvestigation.id),
            osintApi.getInvestigationGraph(activeInvestigation.id),
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

    return () => {
      ws.close();
    };
  }, [activeInvestigation?.id, activeInvestigation?.status]);

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
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          currentView={currentView}
          onNavigate={setCurrentView}
          hasActiveInvestigation={Boolean(activeInvestigation)}
        />

        <main className="flex-1 overflow-y-auto bg-[#080D16]">
          {currentView === 'overview' && (
            <OverviewView
              investigation={activeInvestigation}
              connectors={connectors}
              settings={settings}
              onNavigate={setCurrentView}
            />
          )}

          {currentView === 'search' && (
            <UniversalSearchView
              onStartInvestigation={handleStartInvestigation}
              onNavigate={setCurrentView}
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
            <IntelligenceGraphView
              graph={graph}
              onRefresh={checkActiveInvestigation}
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
        </main>
      </div>
    </div>
  );
};

export default App;
