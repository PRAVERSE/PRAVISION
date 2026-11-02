import asyncio
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel, MatchType
from app.intelligence.entity_resolution import entity_resolution
from app.intelligence.graph_analytics import graph_analytics
from app.intelligence.timeline_engine import timeline_engine
from app.intelligence.threat_intel import threat_intel_engine
from app.intelligence.document_intel import document_intel
from app.intelligence.ai_assistant import intelligence_assistant

def test_intelligence_suite():
    print("Testing Intelligence Suite...")

    # 1. Entity Resolution
    f1 = EvidenceFinding(
        investigation_id="inv1",
        entity_type=EntityType.USERNAME,
        entity_value="johndoe",
        source_name="Sherlock",
        confidence=ConfidenceLevel.HIGH
    )
    f2 = EvidenceFinding(
        investigation_id="inv1",
        entity_type=EntityType.EMAIL,
        entity_value="johndoe@gmail.com",
        source_name="GHunt",
        confidence=ConfidenceLevel.CORROBORATED
    )
    f3 = EvidenceFinding(
        investigation_id="inv1",
        entity_type=EntityType.DOMAIN,
        entity_value="example.com",
        source_name="DNSx",
        confidence=ConfidenceLevel.HIGH
    )
    f4 = EvidenceFinding(
        investigation_id="inv1",
        entity_type=EntityType.SUBDOMAIN,
        entity_value="api.example.com",
        source_name="crt.sh",
        confidence=ConfidenceLevel.HIGH
    )

    res = entity_resolution.resolve_findings([f1, f2, f3, f4])
    print("Entity Resolution:", res)
    assert res["unique_resolved_entities"] == 4
    assert len(res["identity_clusters"]) >= 1

    # 2. Graph Analytics
    nodes = [
        {"id": "n1", "label": "johndoe", "type": "username"},
        {"id": "n2", "label": "johndoe@gmail.com", "type": "email"},
        {"id": "n3", "label": "example.com", "type": "domain"},
        {"id": "n4", "label": "api.example.com", "type": "subdomain"},
    ]
    edges = [
        {"source": "n1", "target": "n2", "relationship": "USES_EMAIL"},
        {"source": "n1", "target": "n3", "relationship": "OWNS_DOMAIN"},
        {"source": "n3", "target": "n4", "relationship": "HAS_SUBDOMAIN"},
    ]
    graph_res = graph_analytics.analyze_graph(nodes, edges)
    print("Graph Analytics:", graph_res)
    assert graph_res["nodes_count"] == 4
    assert graph_res["edges_count"] == 3
    assert len(graph_res["top_entities"]) > 0

    path = graph_analytics.shortest_path(nodes, edges, "n2", "n4")
    print("Shortest path n2 -> n4:", path)
    assert path == ["n2", "n1", "n3", "n4"]

    gexf_data = graph_analytics.export_gexf(nodes, edges)
    assert "<gexf" in gexf_data

    # 3. Timeline Engine
    timeline_res = timeline_engine.process_timeline([f1, f2, f3, f4])
    print("Timeline Events:", timeline_res["total_events"])
    assert timeline_res["total_events"] == 4

    # 4. Threat Intel Engine
    f_threat = EvidenceFinding(
        investigation_id="inv1",
        entity_type=EntityType.IP_ADDRESS,
        entity_value="198.51.100.1",
        source_name="GreyNoise",
        raw_payload={"classification": "malicious", "actor": "MiraiBot"}
    )
    threat_res = threat_intel_engine.evaluate_threat_posture([f1, f2, f_threat])
    print("Threat Intel Posture:", threat_res)
    assert threat_res["overall_risk_score"] > 0
    assert threat_res["is_known_malicious"] is True

    # 5. Document Intel Engine
    sample_text = "Suspect John Doe used email target@evil.com and server 192.168.1.50 with wallet 1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa regarding CVE-2023-38606"
    doc_res = document_intel.extract_entities_from_text(sample_text)
    print("Document Intel Extracted:", doc_res)
    assert "target@evil.com" in doc_res["emails"]
    assert "192.168.1.50" in doc_res["ip_addresses"]
    assert "CVE-2023-38606" in doc_res["cves"]

    # 6. AI Assistant Engine
    briefing = intelligence_assistant.generate_executive_briefing(
        target_input="johndoe",
        target_type="username",
        findings=[f1, f2, f3, f4, f_threat],
        graph_data={"nodes": nodes, "edges": edges},
        threat_posture=threat_res
    )
    print("AI Assistant Briefing Title:", briefing["title"])
    assert "Executive Intelligence Assessment" in briefing["title"]
    assert len(briefing["recommended_next_actions"]) > 0

    qa_res = intelligence_assistant.answer_query("What email was discovered?", "johndoe", [f1, f2], {"nodes": nodes, "edges": edges})
    print("AI Assistant QA:", qa_res)
    assert qa_res["total_matches"] >= 1

    print("ALL INTELLIGENCE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_intelligence_suite()

