import React, { useState, useEffect, useMemo, useRef } from 'react';
import { 
  Share2, 
  ZoomIn, 
  ZoomOut, 
  RotateCcw, 
  Search, 
  Filter, 
  ExternalLink, 
  ShieldCheck, 
  Layers, 
  X 
} from 'lucide-react';
import { IntelligenceGraph, GraphNode, GraphEdge } from '../types/osint';

interface IntelligenceGraphViewProps {
  graph: IntelligenceGraph;
  onRefresh?: () => void;
}

export const IntelligenceGraphView: React.FC<IntelligenceGraphViewProps> = ({ graph }) => {
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Compute 2D node layout positions in a circle/force layout
  const layoutNodes = useMemo(() => {
    const nodes = graph.nodes;
    if (nodes.length === 0) return [];
    const width = 800;
    const height = 500;
    const centerX = width / 2;
    const centerY = height / 2;

    // Check root
    const root = nodes.find(n => n.properties?.root_investigation_target);
    const nonRoots = nodes.filter(n => !n.properties?.root_investigation_target);

    const positions: Array<{ node: GraphNode; x: number; y: number }> = [];

    if (root) {
      positions.push({ node: root, x: centerX, y: centerY });
    }

    const count = nonRoots.length;
    const radius = Math.min(width, height) * 0.38;

    nonRoots.forEach((node, idx) => {
      const angle = (idx / (count || 1)) * 2 * Math.PI;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);
      positions.push({ node, x, y });
    });

    return positions;
  }, [graph.nodes]);

  const nodePosMap = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    layoutNodes.forEach(item => map.set(item.node.id, { x: item.x, y: item.y }));
    return map;
  }, [layoutNodes]);

  const filteredNodes = useMemo(() => {
    if (!searchQuery.trim()) return layoutNodes;
    return layoutNodes.filter(item => 
      item.node.label.toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.node.type.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [layoutNodes, searchQuery]);

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (isDragging) {
      setPan({ x: e.clientX - dragStart.x, y: e.clientY - dragStart.y });
    }
  };

  const handleMouseUp = () => setIsDragging(false);

  const getNodeColor = (type: string, isRoot?: boolean) => {
    if (isRoot) return '#38BDF8';
    switch (type) {
      case 'email': return '#F43F5E';
      case 'username': return '#A855F7';
      case 'domain':
      case 'subdomain': return '#38BDF8';
      case 'ip_address': return '#EAB308';
      case 'geo_coordinate':
      case 'location_place': return '#10B981';
      case 'image': return '#EC4899';
      case 'hash': return '#6366F1';
      case 'breach_record': return '#EF4444';
      default: return '#64748B';
    }
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex overflow-hidden relative select-none">
      {/* Graph Visual Area */}
      <div 
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className="flex-1 bg-[#080D16] relative overflow-hidden cursor-grab active:cursor-grabbing"
      >
        {/* Background Grid Pattern */}
        <div 
          className="absolute inset-0 opacity-15 pointer-events-none"
          style={{
            backgroundImage: `radial-gradient(#38BDF8 1px, transparent 1px)`,
            backgroundSize: '24px 24px'
          }}
        />

        {/* Toolbar */}
        <div className="absolute top-6 left-6 z-20 flex items-center space-x-3">
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search graph entities..."
              className="bg-[#121D2D]/90 backdrop-blur-md border border-[#26364B] rounded-xl px-4 py-2 pl-9 text-xs text-[#F8FAFC] placeholder-[#64748B] focus:outline-none w-64 shadow-xl"
            />
            <Search className="w-3.5 h-3.5 text-sky-400 absolute left-3 top-1/2 -translate-y-1/2" />
          </div>

          <div className="flex items-center space-x-1 bg-[#121D2D]/90 backdrop-blur-md border border-[#26364B] rounded-xl p-1 shadow-xl">
            <button 
              onClick={() => setZoom(z => Math.min(2.5, z + 0.2))} 
              className="p-1.5 hover:bg-[#1E293B] rounded text-[#94A3B8] hover:text-[#F8FAFC] cursor-pointer" 
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <button 
              onClick={() => setZoom(z => Math.max(0.4, z - 0.2))} 
              className="p-1.5 hover:bg-[#1E293B] rounded text-[#94A3B8] hover:text-[#F8FAFC] cursor-pointer" 
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button 
              onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} 
              className="p-1.5 hover:bg-[#1E293B] rounded text-[#94A3B8] hover:text-[#F8FAFC] cursor-pointer" 
              title="Reset View"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* SVG Canvas for Edges and Nodes */}
        <svg 
          className="w-full h-full pointer-events-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0'
          }}
        >
          {/* Edges */}
          <g>
            {graph.edges.map((edge) => {
              const srcPos = nodePosMap.get(edge.source);
              const tgtPos = nodePosMap.get(edge.target);
              if (!srcPos || !tgtPos) return null;

              const midX = (srcPos.x + tgtPos.x) / 2;
              const midY = (srcPos.y + tgtPos.y) / 2;

              return (
                <g key={edge.id}>
                  <line
                    x1={srcPos.x}
                    y1={srcPos.y}
                    x2={tgtPos.x}
                    y2={tgtPos.y}
                    stroke="#26364B"
                    strokeWidth="1.5"
                    strokeDasharray={edge.confidence === 'unverified' ? '4,4' : 'none'}
                  />
                  <text
                    x={midX}
                    y={midY - 4}
                    fill="#64748B"
                    fontSize="9"
                    textAnchor="middle"
                    className="font-mono"
                  >
                    {edge.relation}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {/* HTML Interactive Nodes on Top */}
        <div 
          className="absolute inset-0 pointer-events-none"
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0'
          }}
        >
          {filteredNodes.map(({ node, x, y }) => {
            const isSelected = selectedNode?.id === node.id;
            const isRoot = node.properties?.root_investigation_target;
            const color = getNodeColor(node.type, isRoot);

            return (
              <div
                key={node.id}
                onClick={(e) => { e.stopPropagation(); setSelectedNode(node); }}
                style={{
                  left: `${x}px`,
                  top: `${y}px`,
                  transform: 'translate(-50%, -50%)',
                }}
                className={`absolute pointer-events-auto cursor-pointer p-2 rounded-xl transition-all flex items-center space-x-2 ${
                  isSelected 
                    ? 'ring-2 ring-sky-400 bg-[#121D2D] shadow-2xl z-30 scale-110' 
                    : 'bg-[#0E1624]/90 border border-[#26364B] hover:border-sky-500/50 shadow-lg'
                }`}
              >
                <div 
                  className="w-3.5 h-3.5 rounded-full shrink-0 shadow-sm"
                  style={{ backgroundColor: color }}
                />
                <div className="max-w-[140px] truncate text-xs font-semibold text-[#F8FAFC]">
                  {node.label}
                </div>
              </div>
            );
          })}
        </div>

        {graph.nodes.length === 0 && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-8 space-y-2 pointer-events-none">
            <Share2 className="w-12 h-12 text-[#26364B]" />
            <div className="text-sm font-semibold text-[#94A3B8]">Intelligence Graph is Empty</div>
            <div className="text-xs text-[#64748B]">Correlated nodes and evidence links will populate automatically once an investigation yields findings.</div>
          </div>
        )}
      </div>

      {/* Selected Node Evidence Detail Drawer */}
      {selectedNode && (
        <div className="w-96 bg-[#0E1624] border-l border-[#26364B] p-6 overflow-y-auto space-y-6 shadow-2xl z-40">
          <div className="flex items-center justify-between border-b border-[#26364B] pb-4">
            <div className="space-y-0.5">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                {selectedNode.type}
              </span>
              <h3 className="text-base font-bold text-[#F8FAFC] truncate max-w-[220px]">
                {selectedNode.label}
              </h3>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-1 rounded hover:bg-[#1E293B] text-[#94A3B8] hover:text-[#F8FAFC] cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="space-y-4 text-xs">
            <div>
              <span className="text-[#94A3B8] block mb-1 font-semibold uppercase text-[10px]">Confidence Rating:</span>
              <span className="font-mono text-emerald-400 font-bold uppercase">{selectedNode.confidence}</span>
            </div>

            <div>
              <span className="text-[#94A3B8] block mb-1 font-semibold uppercase text-[10px]">Attributed Sources:</span>
              <div className="flex flex-wrap gap-1">
                {selectedNode.sources.map((s) => (
                  <span key={s} className="px-2 py-0.5 rounded bg-[#121D2D] border border-[#26364B] text-[#CBD5E1] text-[11px]">
                    {s}
                  </span>
                ))}
              </div>
            </div>

            {selectedNode.properties?.source_url && (
              <div>
                <span className="text-[#94A3B8] block mb-1 font-semibold uppercase text-[10px]">Origin URL:</span>
                <a 
                  href={selectedNode.properties.source_url} 
                  target="_blank" 
                  rel="noreferrer"
                  className="text-sky-400 hover:underline flex items-center space-x-1 break-all"
                >
                  <span>{selectedNode.properties.source_url}</span>
                  <ExternalLink className="w-3 h-3 shrink-0" />
                </a>
              </div>
            )}

            {selectedNode.properties?.evidence_description && (
              <div className="p-3 rounded-lg bg-[#121D2D] border border-[#26364B]">
                <span className="text-[#94A3B8] block mb-1 font-semibold uppercase text-[10px]">Evidence Description:</span>
                <p className="text-[#CBD5E1] leading-relaxed">{selectedNode.properties.evidence_description}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

