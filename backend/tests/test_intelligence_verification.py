import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.intelligence.entity_resolution import entity_resolution
from app.intelligence.graph_analytics import graph_analytics
from app.intelligence.timeline_engine import timeline_engine
from app.intelligence.threat_intel import threat_intel_engine
from app.intelligence.ai_assistant import intelligence_assistant

def test_entity_resolution_no_false_merges():
    print("-" * 60)
    print("TEST 1: Entity Resolution - No False Merges on Similar Names")
    print("-" * 60)
    
    # Subtest 1A: Similar names WITHOUT corroborating evidence
    # John Smith vs John Smyth (Jaro-Winkler ~0.93)
    res_unlinked = entity_resolution.compare_entities(
        val1="John Smith",
        type1=EntityType.PERSON_NAME,
        val2="John Smyth",
        type2=EntityType.PERSON_NAME,
        props1={},
        props2={}
    )
    print("Similar Names (No Corroboration):", res_unlinked)
    assert res_unlinked["is_match"] is False, "CRITICAL ERROR: Similar names were falsely merged without corroborating evidence!"
    assert res_unlinked["match_type"] == MatchType.POSSIBLE_MATCH
    assert "candidate flagged; not merged without corroborating evidence" in res_unlinked["reason"]
    print("Verified: Similar names are NOT merged without corroboration.")

    # Subtest 1B: Similar names WITH corroborating evidence (shared phone/email)
    res_corroborated = entity_resolution.compare_entities(
        val1="John Smith",
        type1=EntityType.PERSON_NAME,
        val2="John Smyth",
        type2=EntityType.PERSON_NAME,
        props1={"email": "jsmith@targetcorp.com", "location": "London"},
        props2={"email": "jsmith@targetcorp.com", "location": "London"}
    )
    print("Similar Names (With Corroborating Email):", res_corroborated)
    assert res_corroborated["is_match"] is True
    assert res_corroborated["match_type"] == MatchType.HEURISTIC_MATCH
    assert "corroborated by Shared email" in res_corroborated["reason"]
    print("Verified: Similar names ARE merged when corroborated by shared email.")

    # Subtest 1C: Contradiction Detection (Geographic and Birth Year Conflict)
    res_conflict = entity_resolution.compare_entities(
        val1="Alex Turner",
        type1=EntityType.PERSON_NAME,
        val2="Alex Turner",
        type2=EntityType.PERSON_NAME,
        props1={"location": "London, UK", "birth_year": 1985},
        props2={"location": "Tokyo, Japan", "birth_year": 1999}
    )
    print("Identical Name with Property Conflicts:", res_conflict)
    # Even if exact match on name, property contradiction should flag conflicts
    # Let's check pairwise resolution with contradictions
    findings_conflict = [
        EvidenceFinding(
            investigation_id="inv_c1",
            entity_type=EntityType.PERSON_NAME,
            entity_value="Dmitry Ivanov",
            source_name="SrcA",
            raw_payload={"location": "Moscow, Russia", "dob": "1975"}
        ),
        EvidenceFinding(
            investigation_id="inv_c1",
            entity_type=EntityType.PERSON_NAME,
            entity_value="Dmitri Ivanov",
            source_name="SrcB",
            raw_payload={"location": "Miami, USA", "dob": "1992"}
        )
    ]
    resolved = entity_resolution.resolve_findings(findings_conflict)
    print("Pairwise Resolution on Conflicting Targets:", resolved)
    assert len(resolved["detected_contradictions"]) >= 1
    print("Verified: Contradiction detection flags geographic/birth conflicts.")

    # Subtest 1D: Email-to-Username Heuristic
    res_email_user = entity_resolution.compare_entities(
        val1="vladimir_target@protonmail.com",
        type1=EntityType.EMAIL,
        val2="vladimir_target",
        type2=EntityType.USERNAME
    )
    print("Email to Username Resolution:", res_email_user)
    assert res_email_user["is_match"] is True
    assert res_email_user["match_type"] == MatchType.HEURISTIC_MATCH

    # Subtest 1E: Subdomain Structural Resolution
    res_subdomain = entity_resolution.compare_entities(
        val1="internal.api.defence.gov",
        type1=EntityType.SUBDOMAIN,
        val2="defence.gov",
        type2=EntityType.DOMAIN
    )
    print("Subdomain to Domain Structural Resolution:", res_subdomain)
    assert res_subdomain["is_match"] is True
    assert res_subdomain["match_type"] == MatchType.STRUCTURAL_MATCH
    print("Entity Resolution Verification PASSED!")

def test_graph_analytics_networkx():
    print("-" * 60)
    print("TEST 2: NetworkX Graph Analytics & Gephi GEXF Export")
    print("-" * 60)
    
    nodes = [
        {"id": "node_hub", "label": "Chief Coordinator", "type": "person_name"},
        {"id": "node_broker", "label": "proxy.infra.net", "type": "domain"},
        {"id": "node_server_1", "label": "198.51.100.10", "type": "ip_address"},
        {"id": "node_server_2", "label": "198.51.100.20", "type": "ip_address"},
        {"id": "node_client", "label": "operative_99", "type": "username"}
    ]
    edges = [
        {"source": "node_hub", "target": "node_broker", "relationship": "CONTROLS"},
        {"source": "node_broker", "target": "node_server_1", "relationship": "HOSTED_ON"},
        {"source": "node_broker", "target": "node_server_2", "relationship": "HOSTED_ON"},
        {"source": "node_client", "target": "node_hub", "relationship": "REPORTS_TO"}
    ]

    metrics = graph_analytics.analyze_graph(nodes, edges)
    print("Graph Analytics Metrics:")
    print(f"  Nodes: {metrics['nodes_count']}, Edges: {metrics['edges_count']}, Density: {metrics['density']}")
    print(f"  Communities: {metrics['communities_count']}")
    print("  Top Ranked Entities:")
    for ent in metrics["top_entities"]:
        print(f"    - {ent['label']} ({ent['type']}): PageRank={ent['pagerank']}, Betweenness={ent['betweenness_centrality']}, Degree={ent['degree_centrality']}")

    assert metrics["nodes_count"] == 5
    assert metrics["edges_count"] == 4
    # The broker and hub must have highest centrality
    top_ids = [e["id"] for e in metrics["top_entities"][:2]]
    assert "node_hub" in top_ids or "node_broker" in top_ids

    # Shortest path test
    path = graph_analytics.shortest_path(nodes, edges, "node_client", "node_server_1")
    print(f"Shortest Path from 'node_client' to 'node_server_1': {path}")
    assert path == ["node_client", "node_hub", "node_broker", "node_server_1"]

    # GEXF Export test
    gexf_data = graph_analytics.export_gexf(nodes, edges)
    print(f"GEXF Export Length: {len(gexf_data)} bytes")
    assert "<gexf" in gexf_data
    assert "<nodes>" in gexf_data
    assert "<edges>" in gexf_data
    assert "Chief Coordinator" in gexf_data
    print("NetworkX Graph Analytics Verification PASSED!")

def test_timeline_engine():
    print("-" * 60)
    print("TEST 3: Timeline Engine & Burst Detection")
    print("-" * 60)
    
    t0 = datetime(2025, 6, 1, 10, 0, 0)
    findings = [
        EvidenceFinding(
            investigation_id="inv_time",
            entity_type=EntityType.DOMAIN,
            entity_value="target.org",
            source_name="WhoisXML",
            collection_timestamp=t0 + timedelta(days=10),
            raw_payload={"created_at": (t0 + timedelta(days=10)).isoformat()}
        ),
        EvidenceFinding(
            investigation_id="inv_time",
            entity_type=EntityType.DNS_RECORD,
            entity_value="target.org A 198.51.100.1",
            source_name="DNSx",
            collection_timestamp=t0 + timedelta(days=10, hours=1),
            raw_payload={"created_at": (t0 + timedelta(days=10, hours=1)).isoformat()}
        ),
        EvidenceFinding(
            investigation_id="inv_time",
            entity_type=EntityType.URL,
            entity_value="https://target.org",
            source_name="Certipy",
            collection_timestamp=t0 + timedelta(days=10, hours=2),
            raw_payload={"not_before": (t0 + timedelta(days=10, hours=2)).isoformat()}
        ),
        EvidenceFinding(
            investigation_id="inv_time",
            entity_type=EntityType.URL,
            entity_value="https://target.org/login",
            source_name="WhatWeb",
            collection_timestamp=t0 + timedelta(days=10, hours=3),
            raw_payload={"firstseen": (t0 + timedelta(days=10, hours=3)).isoformat()}
        ),
        EvidenceFinding(
            investigation_id="inv_time",
            entity_type=EntityType.EMAIL,
            entity_value="admin@target.org",
            source_name="Hunter",
            collection_timestamp=t0 + timedelta(days=45),
            raw_payload={"firstseen": (t0 + timedelta(days=45)).isoformat()}
        )
    ]

    timeline = timeline_engine.process_timeline(findings)
    print("Generated Timeline Summary:")
    print(f"  Total Events: {timeline['total_events']}")
    print(f"  Date Range: {timeline.get('earliest_event')} to {timeline.get('latest_event')}")
    print(f"  Detected Bursts: {len(timeline['detected_bursts'])}")
    for b in timeline["detected_bursts"]:
        print(f"    - Burst: {b['event_count']} events in window ({b['start_time']}) - {b['description']}")

    assert timeline["total_events"] == 5
    # Events 1, 2, 3, 4 occurred within 3 hours -> burst detected (density >= 4)
    assert len(timeline["detected_bursts"]) >= 1
    assert timeline["events"][0]["entity_value"] == "target.org"
    print("Timeline Engine Verification PASSED!")

def test_threat_intel_engine():
    print("-" * 60)
    print("TEST 4: Threat Intelligence Aggregation & Severity Scoring")
    print("-" * 60)
    
    findings = [
        EvidenceFinding(
            investigation_id="threat_inv",
            entity_type=EntityType.IP_ADDRESS,
            entity_value="198.51.100.99",
            source_name="GreyNoise Intelligence",
            evidence_description="Scanner flagged as malicious",
            raw_payload={"classification": "malicious", "actor": "MiraiBot"}
        ),
        EvidenceFinding(
            investigation_id="threat_inv",
            entity_type=EntityType.IP_ADDRESS,
            entity_value="198.51.100.99",
            source_name="AbuseIPDB",
            evidence_description="Reported 85 times for brute-force attacks",
            raw_payload={"abuseConfidenceScore": 85}
        ),
        EvidenceFinding(
            investigation_id="threat_inv",
            entity_type=EntityType.DOMAIN,
            entity_value="c2-server.evil.biz",
            source_name="URLhaus / OpenOSINT",
            evidence_description="Active payload delivery host",
            raw_payload={"url_count": 14}
        )
    ]

    posture = threat_intel_engine.evaluate_threat_posture(findings)
    print("Threat Posture Assessment:", posture)
    assert posture["overall_risk_score"] >= 80
    assert posture["severity_level"] == "CRITICAL"
    assert posture["is_known_malicious"] is True
    assert "MiraiBot" in posture["identified_actors"]
    assert len(posture["indicators"]) >= 3
    print("Threat Intel Verification PASSED!")

def test_ai_assistant_grounding():
    print("-" * 60)
    print("TEST 5: AI Assistant Grounded Reasoning & Factual Summarization")
    print("-" * 60)
    
    findings = [
        EvidenceFinding(
            investigation_id="inv_ai_test",
            entity_type=EntityType.DOMAIN,
            entity_value="syndicate-infra.net",
            source_name="WhoisXML",
            evidence_description="Registered with PrivacyProtect LLC on 2024-03-15",
            confidence=ConfidenceLevel.HIGH
        ),
        EvidenceFinding(
            investigation_id="inv_ai_test",
            entity_type=EntityType.IP_ADDRESS,
            entity_value="203.0.113.55",
            source_name="DNSx Multi-Record Resolver",
            evidence_description="A-Record pointing to AS9901 HostEurope in Frankfurt, Germany",
            confidence=ConfidenceLevel.CORROBORATED
        )
    ]
    graph_data = {
        "nodes": [
            {"id": "n1", "label": "syndicate-infra.net", "type": "domain"},
            {"id": "n2", "label": "203.0.113.55", "type": "ip_address"}
        ],
        "edges": [
            {"source": "syndicate-infra.net", "target": "203.0.113.55", "relationship": "RESOLVES_TO"}
        ]
    }

    briefing = intelligence_assistant.generate_executive_briefing(
        target_input="syndicate-infra.net",
        target_type="domain",
        findings=findings,
        graph_data=graph_data
    )
    print("Executive Briefing Output:", briefing["executive_summary"])
    assert "syndicate-infra.net" in briefing["executive_summary"]
    assert briefing["metrics"]["total_findings"] == 2
    assert briefing["metrics"]["graph_nodes"] == 2

    # Query QA Test
    qa_res = intelligence_assistant.answer_query(
        query="What IP address does syndicate-infra.net resolve to?",
        target_input="syndicate-infra.net",
        findings=findings,
        graph_data=graph_data
    )
    print(f"QA Response: {qa_res['answer']}")
    print(f"Matched Artifacts: {qa_res['matched_artifacts']}")
    assert qa_res["total_matches"] >= 1
    assert any(a["entity"] in ("syndicate-infra.net", "203.0.113.55") for a in qa_res["matched_artifacts"])
    print("AI Assistant Grounded Reasoning Verification PASSED!")

def main():
    print("=" * 80)
    print("PRAVISION INTELLIGENCE SUITE INDEPENDENT VERIFICATION")
    print("=" * 80)
    test_entity_resolution_no_false_merges()
    test_graph_analytics_networkx()
    test_timeline_engine()
    test_threat_intel_engine()
    test_ai_assistant_grounding()
    print("\nALL INTELLIGENCE SUITE TESTS COMPLETED AND VERIFIED SUCCESSFULLY.")

if __name__ == "__main__":
    main()
