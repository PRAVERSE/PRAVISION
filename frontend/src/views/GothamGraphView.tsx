import React, { useState, useEffect } from 'react';
import { 
  Share2, 
  Filter, 
  Download, 
  Route, 
  Layers, 
  Activity, 
  Info, 
  ShieldCheck, 
  Maximize2,
  Minimize2,
  ChevronRight
} from 'lucide-react';
import { osintApi } from '../services/api';
import { IntelligenceGraph, GraphNode, EvidenceFinding, GraphAnalyticsResult } from '../types/osint';

interface GothamGraphViewProps {
  graph: IntelligenceGraph;
  findings: EvidenceFinding[];
}

export const GothamGraphView: React.FC<GothamGraphViewProps> = ({ graph, findings }) => {
  const [analytics, setAnalytics] = useState<GraphAnalyticsResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedCommunity, setSelectedCommunity] = useState<string>('all');
  const [minCentrality, setMinCentrality] = useState<number>(0);
  
  // Shortest path tool state
  const [pathSource, setPathSource] = useState<string>('');
  const [pathTarget, setPathTarget] = useState<string>('');
  const [shortestPathResult, setShortestPathResult] = useState<string[]>([]);
  const [calculatingPath, setCalculatingPath] = useState<boolean>(false);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        if (graph.nodes.length > 0) {
          const res = await osintApi.getGraphAnalytics();
          setAnalytics(res);
        }
      } catch (err) {
        console.warn('Analytics fetch warning:', err);
      }
    };
    fetchAnalytics();
  }, [graph]);

  const handleComputeShortestPath = async () => {
    if (!pathSource || !pathTarget || pathSource === pathTarget) return;
    setCalculatingPath(true);
    try {
      const res = await osintApi.getShortestPath(pathSource, pathTarget);
      if (res.found) {
        setShortestPathResult(res.path);
      } else {
        alert('No path exists between selected entities.');
        setShortestPathResult([]);
      }
    } catch (err) {
      console.error('Path error:', err);
    } finally {
      setCalculatingPath(false);
    }
  };

  const handleExportGEXF = () => {
    window.open('/api/intelligence/export/gexf', '_blank');
  };

  const filteredNodes = graph.nodes.filter(n => {
    if (filterType !== 'all' && n.type !== filterType) return false;
    const metric = analytics?.all_metrics?.[n.id];
    if (metric && metric.degree_centrality < minCentrality) return false;
    if (selectedCommunity !== 'all' && metric && metric.community_id.toString() !== selectedCommunity) return false;
    return true;
  });

  const nodeEvidence = findings.filter(f => 
    selectedNode && (f.entity_value.toLowerCase() === selectedNode.label.toLowerCase() || f.entity_value === selectedNode.id)
  );

  return (
    <div className="flex h-full bg-[#080D1A] text-slate-200">
      {/* Central Graph Visual Canvas */}
      <div className="flex-1 flex flex-col relative overflow-hidden">
        {/* Top Floating Control Bar */}
        <div className="absolute top-4 left-4 right-4 z-10 flex items-center justify-between pointer-events-none">
          <div className="flex items-center space-x-2 bg-[#0F172A]/90 backdrop-blur border border-[#1E293B] rounded-lg p-2 shadow-xl pointer-events-auto text-xs">
            <span className="font-mono text-sky-400 font-bold flex items-center space-x-1 pl-1">
              <Share2 className="w-4 h-4" />
              <span>GOTHAM LINK GRAPH</span>
            </span>
            <span className="text-slate-600">|</span>
            <span className="text-slate-400">
              Nodes: <strong className="text-white">{filteredNodes.length}</strong> / {graph.nodes.length}
            </span>
            <span className="text-slate-400">
              Edges: <strong className="text-white">{graph.edges.length}</strong>
            </span>
            {analytics && (
              <>
                <span className="text-slate-600">|</span>
                <span className="text-slate-400">
                  Density: <strong className="text-sky-400 font-mono">{analytics.density}</strong>
                </span>
                <span className="text-slate-400">
                  Partitions: <strong className="text-purple-400 font-mono">{analytics.communities_count}</strong>
                </span>
              </>
            )}
          </div>

          <div className="flex items-center space-x-2 pointer-events-auto">
            <button
              onClick={handleExportGEXF}
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-[#0F172A]/90 hover:bg-[#1E293B] border border-[#1E293B] rounded-lg text-xs font-medium text-slate-200 shadow-xl transition cursor-pointer"
              title="Export Gephi GEXF format"
            >
              <Download className="w-3.5 h-3.5 text-sky-400" />
              <span>Export GEXF</span>
            </button>
          </div>
        </div>

        {/* Graph Render Area */}
        <div className="flex-1 bg-[#060913] p-8 pt-20 overflow-y-auto">
          {graph.nodes.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <Share2 className="w-12 h-12 text-slate-700 mb-3" />
              <h3 className="text-base font-semibold text-slate-300">No Relational Graph Available</h3>
              <p className="text-xs text-slate-500 max-w-sm mt-1">Initiate an investigation to construct relationship trees and topological clusters.</p>
            </div>
          ) : (
            <div className="space-y-6 max-w-6xl mx-auto">
              {/* Shortest Path Banner if calculated */}
              {shortestPathResult.length > 0 && (
                <div className="p-3 bg-indigo-950/40 border border-indigo-800/40 rounded-lg text-xs">
                  <div className="flex items-center space-x-2 text-indigo-300 font-semibold mb-2">
                    <Route className="w-4 h-4" />
                    <span>SHORTEST LINK CHAIN ({shortestPathResult.length} HOPS)</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {shortestPathResult.map((nodeId, idx) => {
                      const nodeObj = graph.nodes.find(n => n.id === nodeId);
                      return (
                        <React.Fragment key={nodeId}>
                          <span className="px-2.5 py-1 bg-[#101B33] border border-indigo-500/40 rounded text-sky-300 font-mono">
                            {nodeObj?.label || nodeId}
                          </span>
                          {idx < shortestPathResult.length - 1 && (
                            <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Node Visual Matrix */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {filteredNodes.map(node => {
                  const metric = analytics?.all_metrics?.[node.id];
                  const isSelected = selectedNode?.id === node.id;
                  const isInShortestPath = shortestPathResult.includes(node.id);
                  const commId = metric?.community_id ?? 0;

                  return (
                    <div
                      key={node.id}
                      onClick={() => setSelectedNode(node)}
                      className={`p-3.5 rounded-lg border transition-all cursor-pointer select-none ${
                        isSelected 
                          ? 'bg-sky-950/60 border-sky-400 shadow-lg shadow-sky-950/50' 
                          : isInShortestPath
                            ? 'bg-indigo-950/50 border-indigo-500'
                            : 'bg-[#0E1626] border-[#1E293B] hover:border-slate-600'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-[10px] px-1.5 py-0.5 rounded font-mono uppercase bg-slate-800 text-slate-300 border border-slate-700">
                          {node.type}
                        </span>
                        <div className="flex items-center space-x-1.5">
                          <span className="text-[9px] px-1.5 py-0.2 rounded font-mono bg-purple-950 text-purple-300 border border-purple-800/40">
                            Cluster #{commId}
                          </span>
                          <span className={`text-[9px] px-1.5 py-0.2 rounded font-medium ${
                            node.confidence === 'high' || node.confidence === 'independently_corroborated' 
                              ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/40' 
                              : 'bg-amber-950 text-amber-400 border border-amber-800/40'
                          }`}>
                            {node.confidence}
                          </span>
                        </div>
                      </div>

                      <h4 className="text-xs font-semibold text-white truncate mb-2">{node.label}</h4>

                      {metric && (
                        <div className="grid grid-cols-3 gap-1 pt-2 border-t border-[#1E293B] text-[10px] font-mono">
                          <div>
                            <span className="text-slate-500 block">Degree</span>
                            <span className="text-sky-400 font-bold">{metric.degree_centrality}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">Between</span>
                            <span className="text-indigo-400 font-bold">{metric.betweenness_centrality}</span>
                          </div>
                          <div>
                            <span className="text-slate-500 block">PageRank</span>
                            <span className="text-emerald-400 font-bold">{metric.pagerank}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Drawer: Filters & Node Inspector */}
      <div className="w-88 border-l border-[#1E293B] bg-[#0A1020] flex flex-col shrink-0 text-xs">
        {/* Tab / Drawer Header */}
        <div className="p-4 border-b border-[#1E293B]">
          <h3 className="font-semibold text-white flex items-center space-x-2">
            <Filter className="w-4 h-4 text-sky-400" />
            <span>TOPOLOGY CONTROLS</span>
          </h3>
        </div>

        <div className="p-4 space-y-4 border-b border-[#1E293B]">
          {/* Entity Type Filter */}
          <div>
            <label className="block text-slate-400 text-[11px] font-medium mb-1">Entity Type</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full bg-[#101B33] border border-[#1E293B] rounded p-1.5 text-white focus:outline-none focus:border-sky-500"
            >
              <option value="all">All Types</option>
              {Array.from(new Set(graph.nodes.map(n => n.type))).map(t => (
                <option key={t} value={t}>{t.toUpperCase()}</option>
              ))}
            </select>
          </div>

          {/* Centrality Threshold Slider */}
          <div>
            <div className="flex justify-between text-[11px] mb-1">
              <span className="text-slate-400 font-medium">Min Degree Centrality</span>
              <span className="text-sky-400 font-mono">{minCentrality}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={minCentrality}
              onChange={(e) => setMinCentrality(parseFloat(e.target.value))}
              className="w-full accent-sky-500"
            />
          </div>

          {/* Shortest Path Tool */}
          <div className="pt-2 border-t border-[#1E293B]">
            <span className="block text-slate-400 text-[11px] font-medium mb-1.5 flex items-center space-x-1">
              <Route className="w-3.5 h-3.5 text-indigo-400" />
              <span>Trace Shortest Path Between Nodes</span>
            </span>
            <div className="space-y-2">
              <select
                value={pathSource}
                onChange={(e) => setPathSource(e.target.value)}
                className="w-full bg-[#101B33] border border-[#1E293B] rounded p-1.5 text-white"
              >
                <option value="">Select Origin Node...</option>
                {graph.nodes.map(n => (
                  <option key={n.id} value={n.id}>{n.label} ({n.type})</option>
                ))}
              </select>
              <select
                value={pathTarget}
                onChange={(e) => setPathTarget(e.target.value)}
                className="w-full bg-[#101B33] border border-[#1E293B] rounded p-1.5 text-white"
              >
                <option value="">Select Destination Node...</option>
                {graph.nodes.map(n => (
                  <option key={n.id} value={n.id}>{n.label} ({n.type})</option>
                ))}
              </select>
              <button
                onClick={handleComputeShortestPath}
                disabled={!pathSource || !pathTarget || pathSource === pathTarget || calculatingPath}
                className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded font-medium transition cursor-pointer"
              >
                {calculatingPath ? 'Tracing Path...' : 'Compute Shortest Path'}
              </button>
            </div>
          </div>
        </div>

        {/* Selected Node Details Drawer */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <h3 className="font-semibold text-white flex items-center space-x-2">
            <Info className="w-4 h-4 text-sky-400" />
            <span>NODE INSPECTOR</span>
          </h3>

          {selectedNode ? (
            <div className="space-y-3">
              <div className="p-3 bg-[#101B33] border border-[#1E293B] rounded-lg">
                <span className="text-[10px] uppercase font-mono text-sky-400">{selectedNode.type}</span>
                <h4 className="text-sm font-bold text-white break-all mt-0.5">{selectedNode.label}</h4>
                <div className="flex items-center space-x-2 mt-2">
                  <span className="text-[10px] text-slate-400">Confidence:</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded font-medium bg-emerald-950 text-emerald-400 border border-emerald-800/40">
                    {selectedNode.confidence}
                  </span>
                </div>
              </div>

              {/* Centrality Metrics */}
              {analytics?.all_metrics?.[selectedNode.id] && (
                <div className="p-3 bg-[#101B33] border border-[#1E293B] rounded-lg space-y-2">
                  <span className="text-[10px] uppercase font-mono text-slate-400 font-bold block">Network Centrality</span>
                  <div className="grid grid-cols-3 gap-2 font-mono text-center">
                    <div className="bg-[#0B132B] p-1.5 rounded">
                      <span className="text-[9px] text-slate-500 block">Degree</span>
                      <span className="text-sky-400 font-bold">{analytics.all_metrics[selectedNode.id].degree_centrality}</span>
                    </div>
                    <div className="bg-[#0B132B] p-1.5 rounded">
                      <span className="text-[9px] text-slate-500 block">Between</span>
                      <span className="text-indigo-400 font-bold">{analytics.all_metrics[selectedNode.id].betweenness_centrality}</span>
                    </div>
                    <div className="bg-[#0B132B] p-1.5 rounded">
                      <span className="text-[9px] text-slate-500 block">PageRank</span>
                      <span className="text-emerald-400 font-bold">{analytics.all_metrics[selectedNode.id].pagerank}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Supporting Evidence Cards */}
              <div>
                <span className="text-[10px] uppercase font-mono text-slate-400 font-bold block mb-2">
                  Supporting Evidence ({nodeEvidence.length})
                </span>
                {nodeEvidence.length === 0 ? (
                  <p className="text-[11px] text-slate-500 italic">No direct raw evidence card for this node.</p>
                ) : (
                  <div className="space-y-2">
                    {nodeEvidence.map(ev => (
                      <div key={ev.id} className="p-2.5 bg-[#101B33] border border-[#1E293B] rounded text-[11px]">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-semibold text-sky-400">{ev.source_name}</span>
                          <span className="text-[9px] text-slate-500">{new Date(ev.collection_timestamp).toLocaleTimeString()}</span>
                        </div>
                        <p className="text-slate-300 text-[10px] break-all">{ev.evidence_description || ev.entity_value}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <p className="text-slate-500 text-[11px] text-center pt-8">
              Click on any node in the graph to inspect its network centrality, neighbors, and evidence dossier.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
