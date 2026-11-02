from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from app.graph.graph_engine import GraphEngine

class RelationshipMapper:
    """
    Maps correlated evidence findings into structured relational graph topology.
    """

    def map_findings_to_graph(self, root_input: str, root_type: EntityType, findings: list[EvidenceFinding], graph: GraphEngine):
        root_node = graph.add_or_update_node(
            node_id=root_input,
            label=root_input,
            node_type=root_type,
            confidence=ConfidenceLevel.HIGH,
            source="user_input",
            properties={"root_investigation_target": True}
        )

        for finding in findings:
            child_node = graph.add_or_update_node(
                node_id=finding.entity_value,
                label=finding.entity_value,
                node_type=finding.entity_type,
                confidence=finding.confidence,
                source=finding.source_name,
                properties={
                    "evidence_description": finding.evidence_description,
                    "source_url": finding.source_url,
                    "match_type": finding.match_type.value
                }
            )

            relation = self._determine_relation(root_type, finding.entity_type, finding)
            graph.add_edge(
                source_id=root_node.id,
                target_id=child_node.id,
                relation=relation,
                confidence=finding.confidence,
                source_name=finding.source_name,
                evidence_id=finding.id,
                properties={"source_url": finding.source_url}
            )

            # Map secondary connections if related entities exist
            for rel in finding.related_entities:
                if rel and rel != finding.entity_value:
                    rel_node = graph.add_or_update_node(
                        node_id=rel,
                        label=rel,
                        node_type=EntityType.ORGANIZATION if "." not in rel else EntityType.DOMAIN,
                        confidence=finding.confidence,
                        source=finding.source_name
                    )
                    graph.add_edge(
                        source_id=child_node.id,
                        target_id=rel_node.id,
                        relation="ASSOCIATED_WITH",
                        confidence=finding.confidence,
                        source_name=finding.source_name,
                        evidence_id=finding.id
                    )

    def _determine_relation(self, parent_type: EntityType, child_type: EntityType, finding: EvidenceFinding) -> str:
        if parent_type == EntityType.USERNAME and child_type == EntityType.URL:
            return "PUBLISHED_PROFILE"
        if parent_type == EntityType.EMAIL and child_type == EntityType.BREACH:
            return "EXPOSED_IN"
        if parent_type in (EntityType.DOMAIN, EntityType.SUBDOMAIN) and child_type == EntityType.IP_ADDRESS:
            return "RESOLVES_TO"
        if parent_type in (EntityType.DOMAIN, EntityType.SUBDOMAIN) and child_type == EntityType.DNS_RECORD:
            return "HAS_RECORD"
        if parent_type in (EntityType.DOMAIN, EntityType.SUBDOMAIN) and child_type == EntityType.SUBDOMAIN:
            return "CHILD_SUBDOMAIN"
        if child_type == EntityType.GEO_COORDINATE:
            return "GEOLOCATED_AT"
        if child_type == EntityType.TECHNOLOGY:
            return "RUNS_TECHNOLOGY"
        if child_type == EntityType.HASH:
            return "FINGERPRINT_HASH"
        return "DISCOVERED_REFERENCE"

relationship_mapper = RelationshipMapper()

