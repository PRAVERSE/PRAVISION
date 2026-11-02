import logging
from typing import List, Dict, Any, Optional
import networkx as nx
from networkx.algorithms import community

logger = logging.getLogger("pravision.intelligence.graph_analytics")

class GraphAnalyticsEngine:
    """
    NetworkX-powered graph analysis engine for PRAVISION:
    Calculates network centrality, identifies key brokers, detects communities,
    and analyzes shortest paths between target entities.
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
                confidence=str(n.get("confidence", "moderate"))
            )
        for e in edges:
            src = str(e.get("source"))
            tgt = str(e.get("target"))
            if G.has_node(src) and G.has_node(tgt):
                G.add_edge(
                    src,
                    tgt,
                    relationship=str(e.get("relationship", "CONNECTED_TO")),
                    confidence=str(e.get("confidence", "moderate"))
                )
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
                "key_influencers": [],
                "bridges": [],
                "communities": {}
            }

        # 1. Degree Centrality (Hubs)
        deg_centrality = nx.degree_centrality(G)

        # 2. Betweenness Centrality (Brokers / Bridges)
        bet_centrality = nx.betweenness_centrality(G) if num_nodes > 2 else {n: 0.0 for n in G.nodes()}

        # 3. PageRank (Structural Importance)
        try:
            pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
        except Exception:
            pagerank = {n: 1.0 / num_nodes for n in G.nodes()}

        # 4. Connected Components
        num_components = nx.number_connected_components(G)

        # 5. Community Detection (Greedy Modularity)
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

    def shortest_path(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], source_id: str, target_id: str) -> Optional[List[str]]:
        G = self.to_networkx(nodes, edges)
        if not (G.has_node(source_id) and G.has_node(target_id)):
            return None
        try:
            return nx.shortest_path(G, source=source_id, target=target_id)
        except nx.NetworkXNoPath:
            return None

    def export_gexf(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> str:
        """Exports graph in Gephi GEXF format."""
        G = self.to_networkx(nodes, edges)
        import io
        buf = io.BytesIO()
        nx.write_gexf(G, buf)
        return buf.getvalue().decode("utf-8")

graph_analytics = GraphAnalyticsEngine()

