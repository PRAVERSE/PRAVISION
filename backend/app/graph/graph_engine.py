from typing import List, Dict, Optional
from app.evidence.models import IntelligenceGraph, GraphNode, GraphEdge, EvidenceFinding, EntityType, ConfidenceLevel

class GraphEngine:
    """
    Maintains and constructs the connected intelligence graph from verified evidence findings.
    Only creates relationships when supported by explicit evidence findings.
    """

    def __init__(self):
        self._nodes: Dict[str, GraphNode] = {}
        self._edges: Dict[str, GraphEdge] = {}

    def get_graph(self) -> IntelligenceGraph:
        return IntelligenceGraph(
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values())
        )

    def add_or_update_node(self, node_id: str, label: str, node_type: EntityType, confidence: ConfidenceLevel, source: str, properties: Optional[Dict] = None) -> GraphNode:
        clean_id = f"{node_type.value}:{node_id.strip().lower()}"
        if clean_id in self._nodes:
            existing = self._nodes[clean_id]
            if source not in existing.sources:
                existing.sources.append(source)
            if properties:
                existing.properties.update(properties)
            # Upgrade confidence if new is higher
            conf_hierarchy = [ConfidenceLevel.UNVERIFIED, ConfidenceLevel.LOW, ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH, ConfidenceLevel.CORROBORATED]
            if conf_hierarchy.index(confidence) > conf_hierarchy.index(existing.confidence):
                existing.confidence = confidence
            return existing

        node = GraphNode(
            id=clean_id,
            label=label or node_id,
            type=node_type,
            confidence=confidence,
            sources=[source],
            properties=properties or {}
        )
        self._nodes[clean_id] = node
        return node

    def add_edge(self, source_id: str, target_id: str, relation: str, confidence: ConfidenceLevel, source_name: str, evidence_id: Optional[str] = None, properties: Optional[Dict] = None) -> GraphEdge:
        edge_key = f"{source_id}->{relation}->{target_id}"
        if edge_key in self._edges:
            return self._edges[edge_key]

        edge = GraphEdge(
            id=edge_key,
            source=source_id,
            target=target_id,
            relation=relation,
            confidence=confidence,
            source_name=source_name,
            evidence_id=evidence_id,
            properties=properties or {}
        )
        self._edges[edge_key] = edge
        return edge

    def clear(self):
        self._nodes.clear( )
        self._edges.clear()

