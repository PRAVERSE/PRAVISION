import pytest
import asyncio
from app.engine.input_classifier import input_classifier, InvestigationMode
from app.evidence.models import EntityType, EvidenceFinding, MatchType, ConfidenceLevel
from app.evidence.evidence_validator import evidence_validator
from app.evidence.source_deduplicator import source_deduplicator
from app.evidence.confidence_engine import confidence_engine
from app.graph.graph_engine import GraphEngine
from app.graph.relationship_mapper import relationship_mapper
from app.connectors.registry import connector_registry
from app.privacy.privacy_controller import privacy_controller

def test_input_classifier():
    # Email
    c1 = input_classifier.classify("target@company.org")
    assert c1.detected_type == EntityType.EMAIL
    assert c1.mode == InvestigationMode.EMAIL
    assert c1.is_valid is True

    # Coordinates
    c2 = input_classifier.classify("48.8584, 2.2945")
    assert c2.detected_type == EntityType.GEO_COORDINATE
    assert c2.mode == InvestigationMode.GLOBAL_SITUATIONAL

    # Domain
    c3 = input_classifier.classify("osint-target.com")
    assert c3.detected_type == EntityType.DOMAIN
    assert c3.mode == InvestigationMode.WEBSITE_DOMAIN

    # IP Address
    c4 = input_classifier.classify("192.168.1.1")
    assert c4.detected_type == EntityType.IP_ADDRESS
    assert c4.mode == InvestigationMode.ORGANIZATION_ASSET

    # Username
    c5 = input_classifier.classify("cyber_analyst_99")
    assert c5.detected_type == EntityType.USERNAME
    assert c5.mode == InvestigationMode.PUBLIC_IDENTITY

    # Image
    c6 = input_classifier.classify("sample_photo.jpg")
    assert c6.detected_type == EntityType.IMAGE
    assert c6.mode == InvestigationMode.MEDIA

def test_evidence_validation():
    assert evidence_validator.validate(EntityType.EMAIL, "audit@domain.com") is True
    assert evidence_validator.validate(EntityType.EMAIL, "not_an_email") is False
    assert evidence_validator.validate(EntityType.DOMAIN, "target.co.uk") is True
    assert evidence_validator.validate(EntityType.IP_ADDRESS, "8.8.8.8") is True
    assert evidence_validator.validate(EntityType.IP_ADDRESS, "999.999.999.999") is False

def test_deduplicator_and_confidence():
    f1 = EvidenceFinding(
        investigation_id="test-1",
        entity_type=EntityType.URL,
        entity_value="https://github.com/analyst",
        source_name="Sherlock",
        source_url="https://github.com/analyst",
        evidence_description="Profile 1",
        match_type=MatchType.EXACT_MATCH
    )
    f2 = EvidenceFinding(
        investigation_id="test-1",
        entity_type=EntityType.URL,
        entity_value="https://github.com/analyst",
        source_name="Maigret",
        source_url="https://github.com/analyst",
        evidence_description="Profile 2",
        match_type=MatchType.EXACT_MATCH
    )
    deduped = source_deduplicator.deduplicate([f1, f2])
    assert len(deduped) == 1

    evaluated = confidence_engine.evaluate_findings(deduped)
    assert len(evaluated) == 1
    assert evaluated[0].confidence in (ConfidenceLevel.MODERATE, ConfidenceLevel.HIGH, ConfidenceLevel.CORROBORATED)

def test_graph_engine():
    graph = GraphEngine()
    node1 = graph.add_or_update_node("target_handle", "target_handle", EntityType.USERNAME, ConfidenceLevel.HIGH, "user")
    node2 = graph.add_or_update_node("target@gmail.com", "target@gmail.com", EntityType.EMAIL, ConfidenceLevel.HIGH, "ghunt")
    edge = graph.add_edge(node1.id, node2.id, "LINKED_EMAIL", ConfidenceLevel.HIGH, "ghunt")

    g = graph.get_graph()
    assert len(g.nodes) == 2
    assert len(g.edges) == 1
    assert g.edges[0].relation == "LINKED_EMAIL"

@pytest.mark.asyncio
async def test_connector_registry():
    manifests = connector_registry.get_manifests()
    assert len(manifests) >= 60

    # Verify GHunt connector is registered
    ghunt = connector_registry.get_connector("ghunt")
    assert ghunt is not None
    health = await ghunt.check_health()
    assert health in ("operational", "partial", "auth_required", "config_required")

    # Verify Restricted Catalogue exists and is marked restricted
    pimeyes = connector_registry.get_connector("pimeyes")
    assert pimeyes is not None
    assert pimeyes.category.value == "restricted_security_research"
    pimeyes_health = await pimeyes.check_health()
    assert pimeyes_health == "restricted"

    # Verify 24 Candidate Connectors (Phase 2 Expanded)
    candidate_names = [
        "whatsmyname", "blackbird", "holehe", "urlscan", "crtsh",
        "securitytrails", "greynoise", "abuseipdb", "misp", "yeti",
        "opencti", "opensanctions", "graphistry", "networkx", "gephi",
        "apache_tika", "qgis", "openstreetmap_overpass", "gdelt", "openaleph",
        "followthemoney", "datasette", "intelowl", "openosint"
    ]
    for cname in candidate_names:
        c = connector_registry.get_connector(cname)
        assert c is not None, f"Candidate {cname} must be registered"
        h = await c.check_health()
        assert h in ("operational", "partial", "auth_required", "config_required", "subscription_required")

@pytest.mark.asyncio
async def test_storage_and_cases():
    from app.storage.database import init_db, check_db_health
    from app.storage.case_manager import case_manager
    from app.storage.b2_storage import b2_storage

    await init_db()
    health = await check_db_health()
    assert health["status"] == "healthy"

    # Create Case
    case = await case_manager.create_case(
        title="Pytest Target Dossier",
        description="Automated storage verification",
        created_by="Automated Test",
        classification="CONFIDENTIAL",
        tags=["automated_test"]
    )
    assert case["case_number"].startswith("CASE-")
    assert case["classification"] == "CONFIDENTIAL"

    # List Cases
    cases = await case_manager.list_cases()
    assert len(cases) >= 1

    # Evidence Vault Upload & SHA-256
    test_bytes = b"IMMUTABLE_CHAIN_OF_CUSTODY_TEST_DATA"
    res = await b2_storage.upload_evidence(test_bytes, "test_evidence.bin")
    assert "file_hash" in res
    assert res["file_size"] == len(test_bytes)

    # Download & verify integrity
    downloaded, hash_val = await b2_storage.download_evidence(res["file_key"])
    assert downloaded == test_bytes
    assert hash_val == res["file_hash"]

    # Delete Case
    deleted = await case_manager.delete_case(case["id"])
    assert deleted is True

def test_intelligence_capabilities():
    from app.intelligence.entity_resolution import entity_resolution
    from app.intelligence.graph_analytics import graph_analytics
    from app.intelligence.timeline_engine import timeline_engine
    from app.intelligence.threat_intel import threat_intel_engine
    from app.intelligence.document_intel import document_intel
    from app.intelligence.ai_assistant import intelligence_assistant

    # 1. Entity Resolution
    f1 = EvidenceFinding(
        investigation_id="t1",
        entity_type=EntityType.EMAIL,
        entity_value="analyst@domain.com",
        source_name="GHunt",
        evidence_description="Email found"
    )
    f2 = EvidenceFinding(
        investigation_id="t1",
        entity_type=EntityType.USERNAME,
        entity_value="analyst",
        source_name="Sherlock",
        evidence_description="Username found"
    )
    res = entity_resolution.resolve_findings([f1, f2])
    assert res["unique_resolved_entities"] == 2
    assert len(res["identity_clusters"]) >= 1

    # 2. Graph Analytics (NetworkX)
    nodes = [
        {"id": "A", "label": "analyst", "type": "username"},
        {"id": "B", "label": "analyst@domain.com", "type": "email"},
        {"id": "C", "label": "domain.com", "type": "domain"},
    ]
    edges = [
        {"source": "A", "target": "B", "relationship": "USES_EMAIL"},
        {"source": "B", "target": "C", "relationship": "ON_DOMAIN"},
    ]
    analytics = graph_analytics.analyze_graph(nodes, edges)
    assert analytics["nodes_count"] == 3
    assert analytics["edges_count"] == 2
    assert len(analytics["top_entities"]) == 3

    path = graph_analytics.shortest_path(nodes, edges, "A", "C")
    assert path == ["A", "B", "C"]

    # 3. Timeline Engine
    timeline = timeline_engine.process_timeline([f1, f2])
    assert timeline["total_events"] == 2

    # 4. Threat Intel Engine
    f_threat = EvidenceFinding(
        investigation_id="t1",
        entity_type=EntityType.IP_ADDRESS,
        entity_value="1.2.3.4",
        source_name="GreyNoise",
        raw_payload={"classification": "malicious", "actor": "TestBot"}
    )
    threat = threat_intel_engine.evaluate_threat_posture([f1, f_threat])
    assert threat["overall_risk_score"] > 0
    assert threat["is_known_malicious"] is True

    # 5. Document Intel Engine
    doc_res = document_intel.extract_entities_from_text("Alert: hacker@bad.com on 10.0.0.1 using CVE-2024-1234")
    assert "hacker@bad.com" in doc_res["emails"]
    assert "10.0.0.1" in doc_res["ip_addresses"]
    assert "CVE-2024-1234" in doc_res["cves"]

    # 6. AI Assistant Copilot
    briefing = intelligence_assistant.generate_executive_briefing(
        target_input="analyst",
        target_type="username",
        findings=[f1, f2, f_threat],
        graph_data={"nodes": nodes, "edges": edges},
        threat_posture=threat
    )
    assert "Executive Intelligence Assessment" in briefing["title"]
    assert len(briefing["recommended_next_actions"]) > 0

    qa = intelligence_assistant.answer_query("What email was observed?", "analyst", [f1, f2], {"nodes": nodes, "edges": edges})
    assert qa["total_matches"] >= 1

def test_privacy_controller():
    sanitized = privacy_controller.sanitize_log_message("User email is john.doe@agency.gov with phone +12025550199 and token api_key: secret_xyz1234567890")
    assert "john.doe@agency.gov" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized

