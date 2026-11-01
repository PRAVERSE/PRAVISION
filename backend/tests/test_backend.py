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

def test_privacy_controller():
    sanitized = privacy_controller.sanitize_log_message("User email is john.doe@agency.gov with phone +12025550199 and token api_key: secret_xyz1234567890")
    assert "john.doe@agency.gov" not in sanitized
    assert "[REDACTED_EMAIL]" in sanitized
    assert "[REDACTED_SECRET]" in sanitized
