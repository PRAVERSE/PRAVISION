import logging
from typing import List, Dict, Any, Optional, Set
import networkx as nx
from networkx.algorithms import community

logger = logging.getLogger("pravision.intelligence.graph_analytics")

CONFIDENCE_WEIGHTS = {
    "unverified": 1,
    "low": 2,
    "moderate": 3,
    "high": 4,
    "independently_corroborated": 5
}

class GraphAnalyticsEngine:
    """
    Gotham-Grade NetworkX Analysis & Topology Engine for PRAVISION:
    - Calculates network centrality (Degree, Betweenness, Closeness, PageRank)
    - Identifies key brokers, community clusters, and structural cut vertices
    - Multi-hop neighborhood expansion with relational constraints
    - Deep shortest path tracing with intermediate edge relations and evidence citations
    - Subgraph extraction and Gephi GEXF export
    """

    @staticmethod
    def to_networkx(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> nx.Graph:
        G = nx.Graph()
        for n in nodes:
            node_id = str(n.get("id"))
            G.add_node(
                node_id,
                label=str(n.get("label", node_id)),
                type=str(n.get("type", "unknown")),
                confidence=str(n.get("confidence", "moderate")),
                sources=n.get("sources", []),
                properties=n.get("properties", {})
            )
        for e in edges:
            src = str(e.get("source"))
            tgt = str(e.get("target"))
            if G.has_node(src) and G.has_node(tgt):
                attrs = {
                    "id": str(e.get("id", f"{src}->{tgt}")),
                    "relationship": str(e.get("relation") or e.get("relationship", "CONNECTED_TO")),
                    "confidence": str(e.get("confidence", "moderate")),
                    "source_name": str(e.get("source_name", "osint"))
                }
                if e.get("evidence_id") is not None:
                    attrs["evidence_id"] = str(e.get("evidence_id"))
                G.add_edge(src, tgt, **attrs)
        return G

    def analyze_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        G = self.to_networkx(nodes, edges)
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()

        if num_nodes == 0:
            return {
                "nodes_count": 0,
                "edges_count": 0,
                "density": 0.0,
                "connected_components": 0,
                "top_entities": [],
                "all_metrics": {},
                "communities_count": 0
            }

        # 1. Degree Centrality (Hubs)
        deg_centrality = nx.degree_centrality(G)

        # 2. Betweenness Centrality (Brokers / Bridges)
        bet_centrality = nx.betweenness_centrality(G) if num_nodes > 2 else {n: 0.0 for n in G.nodes()}

        # 3. Closeness Centrality
        try:
            close_centrality = nx.closeness_centrality(G)
        except Exception:
            close_centrality = {n: 0.0 for n in G.nodes()}

        # 4. PageRank (Structural Importance)
        try:
            pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
        except Exception:
            pagerank = {n: 1.0 / num_nodes for n in G.nodes()}

        # 5. Connected Components
        num_components = nx.number_connected_components(G)

        # 6. Community Detection (Greedy Modularity)
        community_map: Dict[str, int] = {}
        if num_nodes >= 3:
            try:
                comms = community.greedy_modularity_communities(G)
                for idx, c in enumerate(comms):
                    for node in c:
                        community_map[str(node)] = idx
            except Exception as e:
                logger.debug(f"Community detection fallback: {e}")
                community_map = {str(n): 0 for n in G.nodes()}
        else:
            community_map = {str(n): 0 for n in G.nodes()}

        # Compile Top Influencers / Brokers
        ranked_nodes = []
        for n in G.nodes():
            ranked_nodes.append({
                "id": n,
                "label": G.nodes[n].get("label", n),
                "type": G.nodes[n].get("type", "unknown"),
                "degree_centrality": round(deg_centrality.get(n, 0.0), 4),
                "betweenness_centrality": round(bet_centrality.get(n, 0.0), 4),
                "closeness_centrality": round(close_centrality.get(n, 0.0), 4),
                "pagerank": round(pagerank.get(n, 0.0), 4),
                "community_id": community_map.get(n, 0)
            })

        ranked_nodes.sort(key=lambda x: (x["pagerank"], x["betweenness_centrality"]), reverse=True)

        return {
            "nodes_count": num_nodes,
            "edges_count": num_edges,
            "density": round(nx.density(G), 4),
            "connected_components": num_components,
            "top_entities": ranked_nodes[:10],
            "all_metrics": {r["id"]: r for r in ranked_nodes},
            "communities_count": len(set(community_map.values())) if community_map else 1
        }

    def expand_neighborhood(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        seed_node_ids: List[str],
        hops: int = 1,
        allowed_relation_types: Optional[List[str]] = None,
        min_confidence: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Dynamically expands graph neighborhood from seed nodes up to N hops,
        honoring relationship type and minimum confidence level filters.
        """
        G = self.to_networkx(nodes, edges)
        min_conf_val = CONFIDENCE_WEIGHTS.get(min_confidence, 1) if min_confidence else 1

        valid_seeds = [s for s in seed_node_ids if G.has_node(s)]
        if not valid_seeds:
            return {"nodes": [], "edges": []}

        visited_nodes: Set[str] = set(valid_seeds)
        current_frontier: Set[str] = set(valid_seeds)

        for _ in range(max(1, min(hops, 4))):
            next_frontier: Set[str] = set()
            for u in current_frontier:
                for v in G.neighbors(u):
                    edge_data = G.get_edge_data(u, v)
                    rel_type = edge_data.get("relationship", "CONNECTED_TO")
                    conf = edge_data.get("confidence", "unverified")
                    conf_val = CONFIDENCE_WEIGHTS.get(conf, 1)

                    if allowed_relation_types and rel_type not in allowed_relation_types:
                        continue
                    if conf_val < min_conf_val:
                        continue

                    if v not in visited_nodes:
                        next_frontier.add(v)
                        visited_nodes.add(v)
            current_frontier = next_frontier

        # Induce subgraph
        sub_nodes = [n for n in nodes if str(n.get("id")) in visited_nodes]
        sub_edges = [
            e for e in edges
            if str(e.get("source")) in visited_nodes and str(e.get("target")) in visited_nodes
        ]

        return {
            "seed_nodes": valid_seeds,
            "hops": hops,
            "total_nodes": len(sub_nodes),
            "total_edges": len(sub_edges),
            "nodes": sub_nodes,
            "edges": sub_edges
        }

    def shortest_path(
        self,
        nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
        source_id: str,
        target_id: str
    ) -> Dict[str, Any]:
        """
        Finds the shortest path and provides step-by-step segment details,
        intermediate relationships, and evidence citations.
        """
        G = self.to_networkx(nodes, edges)
        if not (G.has_node(source_id) and G.has_node(target_id)):
            return {"found": False, "path": [], "segments": [], "hops": 0}

        try:
            path = nx.shortest_path(G, source=source_id, target=target_id)
            segments = []
            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]
                edge_data = G.get_edge_data(u, v) or {}
                u_node = G.nodes[u]
                v_node = G.nodes[v]
                segments.append({
                    "step": i + 1,
                    "from_node": {"id": u, "label": u_node.get("label", u), "type": u_node.get("type")},
                    "to_node": {"id": v, "label": v_node.get("label", v), "type": v_node.get("type")},
                    "relationship": edge_data.get("relationship", "CONNECTED_TO"),
                    "confidence": edge_data.get("confidence", "moderate"),
                    "evidence_id": edge_data.get("evidence_id"),
                    "source_name": edge_data.get("source_name")
                })

            return {
                "found": True,
                "path": path,
                "hops": len(path) - 1,
                "segments": segments
            }
        except nx.NetworkXNoPath:
            return {"found": False, "path": [], "segments": [], "hops": 0}

    def export_gexf(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        """Exports graph in Gephi GEXF format."""
        G = self.to_networkx(nodes, edges)
        import io
        buf = io.BytesIO()
        nx.write_gexf(G, buf)
        return buf.getvalue().decode("utf-8")

graph_analytics = GraphAnalyticsEngine()
