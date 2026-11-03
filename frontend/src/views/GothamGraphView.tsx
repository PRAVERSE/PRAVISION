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
  ChevronRight,
  Search,
  ExternalLink,
  GitBranch,
  Sparkles,
  Eye
} from 'lucide-react';
import { osintApi, API_BASE } from '../services/api';
import { IntelligenceGraph, GraphNode, EvidenceFinding, GraphAnalyticsResult } from '../types/osint';

interface GothamGraphViewProps {
  graph: IntelligenceGraph;
  findings: EvidenceFinding[];
  onSelectEntity?: (entityVal: string) => void;
}

export const GothamGraphView: React.FC<GothamGraphViewProps> = ({ 
  graph, 
  findings,
  onSelectEntity 
}) => {
  const [analytics, setAnalytics] = useState<GraphAnalyticsResult | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<any | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [filterRelation, setFilterRelation] = useState<string>('all');
  const [filterMinConfidence, setFilterMinConfidence] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCommunity, setSelectedCommunity] = useState<string>('all');
  const [minCentrality, setMinCentrality] = useState<number>(0);
  
  // Neighborhood expansion state
  const [subgraphOverride, setSubgraphOverride] = useState<any | null>(null);
  const [isExpanding, setIsExpanding] = useState<boolean>(false);

  // Shortest path tool state
  const [pathSource, setPathSource] = useState<string>('');
  const [pathTarget, setPathTarget] = useState<string>('');
  const [shortestPathData, setShortestPathData] = useState<any | null>(null);
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

  const activeNodes = subgraphOverride ? subgraphOverride.nodes : graph.nodes;
  const activeEdges = subgraphOverride ? subgraphOverride.edges : graph.edges;

  // Multi-hop neighborhood expansion
  const handleExpandNeighborhood = async (hops: number) => {
    if (!selectedNode) return;
    setIsExpanding(true);
    try {
      const res = await osintApi.expandGraphNeighborhood(
        [selectedNode.id],
        hops,
        filterRelation !== 'all' ? [filterRelation] : undefined,
        filterMinConfidence !== 'all' ? filterMinConfidence : undefined
      );
      setSubgraphOverride(res);
    } catch (err) {
      console.error('Neighborhood expansion error:', err);
    } finally {
      setIsExpanding(false);
    }
  };

  const handleResetSubgraph = () => {
    setSubgraphOverride(null);
  };

  const handleComputeShortestPath = async () => {
    if (!pathSource || !pathTarget || pathSource === pathTarget) return;
    setCalculatingPath(true);
    try {
      const res = await osintApi.getShortestPath(pathSource, pathTarget);
      if (res.found) {
        setShortestPathData(res);
      } else {
        alert('No link chain exists between selected entities.');
        setShortestPathData(null);
      }
    } catch (err) {
      console.error('Path error:', err);
    } finally {
      setCalculatingPath(false);
    }
  };

  const handleExportGEXF = () => {
    window.open(`${API_BASE}/intelligence/export/gexf`, '_blank');
  };

  const confidenceRank: Record<string, number> = {
    unverified: 1,
    low: 2,
    moderate: 3,
    high: 4,
    independently_corroborated: 5
  };

  const filteredNodes = activeNodes.filter((n: GraphNode) => {
    if (filterType !== 'all' && n.type !== filterType) return false;
    if (searchQuery && !n.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (filterMinConfidence !== 'all') {
      const nRank = confidenceRank[n.confidence] || 1;
      const minRank = confidenceRank[filterMinConfidence] || 1;
      if (nRank < minRank) return false;
    }
    const metric = analytics?.all_metrics?.[n.id];
    if (metric && metric.degree_centrality < minCentrality) return false;
    if (selectedCommunity !== 'all' && metric && metric.community_id.toString() !== selectedCommunity) return false;
    return true;
  });

  const uniqueRelationTypes = Array.from(new Set(graph.edges.map(e => e.relation || 'CONNECTED_TO')));

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
              Edges: <strong className="text-white">{activeEdges.length}</strong>
            </span>
            {subgraphOverride && (
              <>
                <span className="text-slate-600">|</span>
                <span className="px-1.5 py-0.5 bg-amber-950 text-amber-300 border border-amber-800/40 rounded font-mono text-[10px]">
                  SUBGRAPH ({subgraphOverride.hops} HOPS)
                </span>
                <button
                  onClick={handleResetSubgraph}
                  className="px-2 py-0.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-[10px] cursor-pointer"
                >
                  Reset
                </button>
              </>
            )}
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
              {/* Shortest Path Detailed Banner */}
              {shortestPathData && shortestPathData.found && (
                <div className="p-3.5 bg-indigo-950/40 border border-indigo-800/40 rounded-lg text-xs space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2 text-indigo-300 font-semibold">
                      <Route className="w-4 h-4" />
                      <span>SHORTEST LINK CHAIN ({shortestPathData.hops} HOPS)</span>
                    </div>
                    <button
                      onClick={() => setShortestPathData(null)}
                      className="text-slate-400 hover:text-white text-[10px]"
                    >
                      Dismiss
                    </button>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {shortestPathData.path.map((nodeId: string, idx: number) => {
                      const nodeObj = graph.nodes.find(n => n.id === nodeId);
                      return (
                        <React.Fragment key={nodeId}>
                          <span 
                            onClick={() => {
                              if (nodeObj) setSelectedNode(nodeObj);
                            }}
                            className="px-2.5 py-1 bg-[#101B33] border border-indigo-500/40 rounded text-sky-300 font-mono cursor-pointer hover:border-sky-400"
                          >
                            {nodeObj?.label || nodeId}
                          </span>
                          {idx < shortestPathData.path.length - 1 && (
                            <ChevronRight className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>

                  {shortestPathData.segments && shortestPathData.segments.length > 0 && (
                    <div className="pt-2 border-t border-indigo-900/40 grid grid-cols-1 md:grid-cols-2 gap-2 text-[10px]">
                      {shortestPathData.segments.map((seg: any) => (
                        <div key={seg.step} className="p-2 bg-[#0B132B]/60 rounded border border-[#1E293B]">
                          <span className="text-slate-400 block font-mono">Step #{seg.step}: {seg.from_node.label} ➔ {seg.to_node.label}</span>
                          <span className="text-sky-300 font-semibold">{seg.relationship}</span>
                          <span className="text-slate-500 ml-2">({seg.confidence} via {seg.source_name || 'OSINT'})</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Node Visual Matrix */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {filteredNodes.map((node: GraphNode) => {
                  const metric = analytics?.all_metrics?.[node.id];
                  const isSelected = selectedNode?.id === node.id;
                  const isInShortestPath = shortestPathData?.path?.includes(node.id);
                  const commId = metric?.community_id ?? 0;

                  return (
                    <div
                      key={node.id}
                      onClick={() => {
                        setSelectedNode(node);
                        setSelectedEdge(null);
                      }}
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

      {/* Right Analytical Controls & Inspector Sidebar */}
      <div className="w-80 md:w-96 border-l border-[#1E293B] bg-[#0A101D] flex flex-col h-full text-xs">
        {/* Filters and Search Panel */}
        <div className="p-4 border-b border-[#1E293B] space-y-3 bg-[#0F172A]">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-white flex items-center space-x-1.5">
              <Filter className="w-3.5 h-3.5 text-sky-400" />
              <span>GRAPH CONTROLS</span>
            </span>
          </div>

          <div className="space-y-2">
            <div>
              <input
                type="text"
                placeholder="Search node labels..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#131F37] border border-[#1E293B] rounded px-2.5 py-1.5 text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 text-xs"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Entity Type</label>
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded px-2 py-1 text-slate-200 text-xs focus:outline-none"
                >
                  <option value="all">All Types</option>
                  <option value="username">Username</option>
                  <option value="email">Email</option>
                  <option value="domain">Domain</option>
                  <option value="ip_address">IP Address</option>
                  <option value="url">URL</option>
                  <option value="person_name">Person</option>
                  <option value="organization">Organization</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-slate-400 block mb-1">Confidence</label>
                <select
                  value={filterMinConfidence}
                  onChange={(e) => setFilterMinConfidence(e.target.value)}
                  className="w-full bg-[#131F37] border border-[#1E293B] rounded px-2 py-1 text-slate-200 text-xs focus:outline-none"
                >
                  <option value="all">Any Confidence</option>
                  <option value="moderate">Moderate+</option>
                  <option value="high">High+</option>
                  <option value="independently_corroborated">Corroborated</option>
                </select>
              </div>
            </div>
          </div>
        </div>

        {/* Shortest Path Tool */}
        <div className="p-4 border-b border-[#1E293B] space-y-2 bg-[#0C1322]">
          <span className="font-semibold text-white flex items-center space-x-1.5">
            <Route className="w-3.5 h-3.5 text-indigo-400" />
            <span>LINK PATH TRACER</span>
          </span>
          <div className="space-y-1.5">
            <select
              value={pathSource}
              onChange={(e) => setPathSource(e.target.value)}
              className="w-full bg-[#131F37] border border-[#1E293B] rounded px-2 py-1 text-slate-200 text-xs"
            >
              <option value="">Select Origin Entity...</option>
              {graph.nodes.map(n => (
                <option key={n.id} value={n.id}>{n.label} ({n.type})</option>
              ))}
            </select>

            <select
              value={pathTarget}
              onChange={(e) => setPathTarget(e.target.value)}
              className="w-full bg-[#131F37] border border-[#1E293B] rounded px-2 py-1 text-slate-200 text-xs"
            >
              <option value="">Select Target Entity...</option>
              {graph.nodes.map(n => (
                <option key={n.id} value={n.id}>{n.label} ({n.type})</option>
              ))}
            </select>

            <button
              onClick={handleComputeShortestPath}
              disabled={calculatingPath || !pathSource || !pathTarget}
              className="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white rounded font-medium transition cursor-pointer"
            >
              {calculatingPath ? 'Tracing Path...' : 'Compute Shortest Path'}
            </button>
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

                {/* Actions: Multi-Hop Expansion & Dossier */}
                <div className="mt-3 pt-2 border-t border-[#1E293B] space-y-2">
                  <span className="text-[10px] font-mono uppercase text-slate-400 block">Expand Neighborhood:</span>
                  <div className="grid grid-cols-3 gap-1">
                    <button
                      onClick={() => handleExpandNeighborhood(1)}
                      disabled={isExpanding}
                      className="px-2 py-1 bg-sky-950 hover:bg-sky-900 border border-sky-800/50 rounded text-sky-200 text-[10px] font-mono cursor-pointer"
                    >
                      1 Hop
                    </button>
                    <button
                      onClick={() => handleExpandNeighborhood(2)}
                      disabled={isExpanding}
                      className="px-2 py-1 bg-sky-950 hover:bg-sky-900 border border-sky-800/50 rounded text-sky-200 text-[10px] font-mono cursor-pointer"
                    >
                      2 Hops
                    </button>
                    <button
                      onClick={() => handleExpandNeighborhood(3)}
                      disabled={isExpanding}
                      className="px-2 py-1 bg-sky-950 hover:bg-sky-900 border border-sky-800/50 rounded text-sky-200 text-[10px] font-mono cursor-pointer"
                    >
                      3 Hops
                    </button>
                  </div>

                  {onSelectEntity && (
                    <button
                      onClick={() => onSelectEntity(selectedNode.label)}
                      className="w-full mt-2 flex items-center justify-center space-x-1.5 py-1.5 bg-emerald-900/50 hover:bg-emerald-800 border border-emerald-700 text-emerald-200 rounded text-xs cursor-pointer"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Open Full Dossier</span>
                    </button>
                  )}
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

export default GothamGraphView;
