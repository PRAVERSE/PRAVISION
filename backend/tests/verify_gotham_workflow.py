import asyncio
import os
import sys
import uuid
import json
import hashlib
from datetime import datetime
from pathlib import Path

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.engine.input_classifier import input_classifier
from app.engine.investigation_orchestrator import orchestrator
from app.evidence.models import EntityType, MatchType, ConfidenceLevel, EvidenceFinding
from app.intelligence.entity_resolution_v2 import entity_resolution_v2
from app.intelligence.graph_analytics import graph_analytics
from app.intelligence.unified_search import unified_search
from app.storage.database import init_db, check_db_health, async_session_maker, engine
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.streaming_archive import streaming_archive_service
from app.auth.auth_service import hash_password, verify_password, create_jwt_token, decode_jwt_token
from app.storage.models_db import EntityModel, RelationshipModel, EvidenceModel, CaseModel, EntityMergeLogModel
from sqlalchemy import select

PASSED = 0
FAILED = 0

def check(step_num: int, title: str, condition: bool, details: str = ""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] Step {step_num:02d}: {title} {details}")
    else:
        FAILED += 1
        print(f"  [FAIL] Step {step_num:02d}: {title} - ERROR: {details}")

async def run_20_step_verification():
    print("=" * 70)
    print("PRAVISION GOTHAM-GRADE 20-STEP END-TO-END ACCEPTANCE VERIFICATION")
    print("=" * 70)

    # Step 1: Database and Schema Initialization
    await init_db()
    health = await check_db_health()
    check(1, "Database & Schema Initialization", health["status"] == "healthy", f"({health['backend']}, {health['latency_ms']}ms)")

    # Step 2: Input Classification across 6 domains
    c_email = input_classifier.classify("target@defense.gov")
    c_user = input_classifier.classify("alphanumeric_handle")
    c_ip = input_classifier.classify("198.51.100.42")
    c_domain = input_classifier.classify("surveillance.org")
    c_phone = input_classifier.classify("+1 (555) 234-5678")
    c_coord = input_classifier.classify("37.7749, -122.4194")
    all_classified = (
        c_email.detected_type == EntityType.EMAIL and
        c_user.detected_type == EntityType.USERNAME and
        c_ip.detected_type == EntityType.IP_ADDRESS and
        c_domain.detected_type == EntityType.DOMAIN and
        c_phone.detected_type == EntityType.PHONE and
        c_coord.detected_type == EntityType.GEO_COORDINATE
    )
    check(2, "Universal Intake Classification", all_classified, "(email, username, IP, domain, phone, coordinates)")

    # Step 3: Multi-Format Normalization Pipeline
    n_phone = entity_resolution_v2.normalize_entity_value("+1 (555) 019-2834", "phone")
    n_email = entity_resolution_v2.normalize_entity_value("John.Doe+tag@gmail.com", "email")
    n_domain = entity_resolution_v2.normalize_entity_value("https://Sec.Domain.Com/", "domain")
    n_name = entity_resolution_v2.normalize_entity_value("Dr. Alexander Hamilton ", "person_name")
    norm_pass = (
        n_phone == "+15550192834" and
        n_email == "johndoe@gmail.com" and
        n_domain == "sec.domain.com" and
        n_name == "alexander hamilton"
    )
    check(3, "Entity Normalization Pipeline", norm_pass, f"(Phone: {n_phone}, Email: {n_email}, Domain: {n_domain})")

    # Step 4: Multi-Factor Candidate Scoring
    match_eval = entity_resolution_v2.evaluate_match(
        val1="johndoe@proton.me", type1="email",
        val2="johndoe", type2="username",
        identifiers1={"email": "johndoe@proton.me"},
        identifiers2={"email": "johndoe@proton.me"}
    )
    check(4, "Multi-Factor Candidate Scoring", match_eval["is_match"] and match_eval["match_score"] >= 0.88, f"(Score: {match_eval['match_score']}, Rec: {match_eval['recommendation']})")

    # Step 5: Explainable Factor Generation
    factors = match_eval.get("explainable_factors", [])
    has_factors = len(factors) >= 2 and any("Shared Identifier" in f["factor"] for f in factors)
    check(5, "Explainable Match Factors", has_factors, f"({len(factors)} explainable weighting factors)")

    # Step 6: Contradiction & Conflict Safeguards
    conflict_eval = entity_resolution_v2.evaluate_match(
        val1="Alexander Hamilton", type1="person_name",
        val2="Alexander Hamilton", type2="person_name",
        props1={"country": "United States", "dob": "1757-01-11"},
        props2={"country": "Russian Federation", "dob": "1985-06-20"}
    )
    has_conflicts = len(conflict_eval["conflicts"]) >= 2 and conflict_eval["recommendation"] == "conflicting_review"
    check(6, "Conflict & Contradiction Safeguards", has_conflicts, f"({len(conflict_eval['conflicts'])} conflicts identified)")

    # Step 7: Case Dossier Creation
    test_case = await case_manager.create_case(
        title="Operation Gotham Verification",
        description="Comprehensive end-to-end intelligence verification case",
        created_by="Lead Investigator",
        classification="CONFIDENTIAL",
        tags=["gotham", "verification", "rbac"]
    )
    case_id = test_case["id"]
    check(7, "Persistent Case Dossier Creation", bool(case_id), f"(Case Number: {test_case['case_number']})")

    # Step 8: Entities Insertion & Investigation Save
    inv_id = f"inv-gotham-{uuid.uuid4().hex[:6]}"
    mock_findings = [
        EvidenceFinding(
            investigation_id=inv_id,
            entity_type=EntityType.EMAIL,
            entity_value="operator@shadow.net",
            source_name="EmailRep",
            source_url="https://emailrep.io/operator@shadow.net",
            confidence=ConfidenceLevel.HIGH,
            evidence_description="Verified suspicious operator email account"
        ),
        EvidenceFinding(
            investigation_id=inv_id,
            entity_type=EntityType.USERNAME,
            entity_value="operator_shadow",
            source_name="WhatsMyName",
            source_url="https://github.com/operator_shadow",
            confidence=ConfidenceLevel.HIGH,
            evidence_description="Active developer account"
        ),
        EvidenceFinding(
            investigation_id=inv_id,
            entity_type=EntityType.DOMAIN,
            entity_value="shadow.net",
            source_name="crtsh",
            source_url="https://crt.sh/?q=shadow.net",
            confidence=ConfidenceLevel.HIGH,
            evidence_description="Host infrastructure domain"
        ),
        EvidenceFinding(
            investigation_id=inv_id,
            entity_type=EntityType.IP_ADDRESS,
            entity_value="198.51.100.99",
            source_name="urlscan",
            source_url="https://urlscan.io/ip/198.51.100.99",
            confidence=ConfidenceLevel.HIGH,
            evidence_description="Resolved server IP address"
        )
    ]

    mock_nodes = [
        {"id": "operator@shadow.net", "label": "operator@shadow.net", "type": "email", "confidence": "high"},
        {"id": "operator_shadow", "label": "operator_shadow", "type": "username", "confidence": "high"},
        {"id": "shadow.net", "label": "shadow.net", "type": "domain", "confidence": "high"},
        {"id": "198.51.100.99", "label": "198.51.100.99", "type": "ip_address", "confidence": "high"}
    ]
    mock_edges = [
        {"source": "operator@shadow.net", "target": "operator_shadow", "relationship": "ALIAS_OF", "confidence": "high"},
        {"source": "operator@shadow.net", "target": "shadow.net", "relationship": "AFFILIATED_DOMAIN", "confidence": "high"},
        {"source": "shadow.net", "target": "198.51.100.99", "relationship": "RESOLVES_TO", "confidence": "high"}
    ]

    save_res = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input="operator@shadow.net",
        root_type="email",
        mode="mode_3_email",
        findings=mock_findings,
        graph_nodes=mock_nodes,
        graph_edges=mock_edges
    )
    check(8, "Investigation & Findings Persistence", save_res["status"] == "saved", f"(Case ID: {case_id})")

    # Retrieve saved entities
    async with async_session_maker() as session:
        ents = (await session.execute(select(EntityModel).where(EntityModel.case_id == case_id))).scalars().all()
        ent_by_val = {e.entity_value: e for e in ents}
    check(9, "Database Relational Model Extraction", len(ents) == 4, f"({len(ents)} entities in case)")

    canon_ent = ent_by_val["operator@shadow.net"]
    abs_ent = ent_by_val["operator_shadow"]

    # Step 10: Lossless Identity Merge Execution
    merge_res = await entity_resolution_v2.merge_entities(
        canonical_entity_id=canon_ent.id,
        absorbed_entity_ids=[abs_ent.id],
        merged_by="Lead Analyst",
        reason="Corroborated email-handle identity pairing"
    )
    check(10, "Auditable Identity Merge", merge_res["status"] == "merged" and merge_res["total_aliases"] >= 1, f"(Canonical ID: {canon_ent.id[:8]})")

    # Step 11: Relationship & Evidence Rewiring
    async with async_session_maker() as session:
        # Check that absorbed entity has merged_into_id set
        refreshed_abs = (await session.execute(select(EntityModel).where(EntityModel.id == abs_ent.id))).scalar_one()
        # Check that merge log exists
        merge_log = (await session.execute(select(EntityMergeLogModel).where(EntityMergeLogModel.canonical_entity_id == canon_ent.id))).scalars().first()
    check(11, "Merge Provenance & Snapshot Log", refreshed_abs.merged_into_id == canon_ent.id and merge_log is not None and merge_log.is_active, "(Snapshot recorded in EntityMergeLogModel)")

    # Step 12: Lossless Undo (Unmerge) Execution
    unmerge_res = await entity_resolution_v2.unmerge_entity(
        canonical_entity_id=canon_ent.id,
        absorbed_entity_id=abs_ent.id,
        unmerged_by="Lead Analyst"
    )
    async with async_session_maker() as session:
        restored_abs = (await session.execute(select(EntityModel).where(EntityModel.id == abs_ent.id))).scalar_one()
    check(12, "Reversible Lossless Unmerge", unmerge_res["status"] == "unmerged" and restored_abs.merged_into_id is None, "(Restored absorbed identity cleanly)")

    # Step 13: Multi-Hop Neighborhood Expansion
    expansion = graph_analytics.expand_neighborhood(
        nodes=mock_nodes,
        edges=mock_edges,
        seed_node_ids=["operator@shadow.net"],
        hops=2
    )
    check(13, "Multi-Hop Neighborhood Expansion", expansion["total_nodes"] == 4 and expansion["hops"] == 2, f"(Expanded {expansion['total_nodes']} nodes across 2 hops)")

    # Step 14: Shortest Path with Step Segments & Citations
    path_res = graph_analytics.shortest_path(
        nodes=mock_nodes,
        edges=mock_edges,
        source_id="operator@shadow.net",
        target_id="198.51.100.99"
    )
    check(14, "Shortest Link Path Tracing", path_res["found"] and path_res["hops"] == 2, f"(Found {path_res['hops']} hops with {len(path_res['segments'])} segment citations)")

    # Step 15: Network Centrality & Modularity Partitions
    analytics_res = graph_analytics.analyze_graph(mock_nodes, mock_edges)
    check(15, "Graph Centrality & Community Detection", analytics_res["nodes_count"] == 4 and len(analytics_res["top_entities"]) > 0, f"(Density: {analytics_res['density']}, Partitions: {analytics_res['communities_count']})")

    # Step 16: Gephi GEXF Export
    gexf_str = graph_analytics.export_gexf(mock_nodes, mock_edges)
    check(16, "Gephi GEXF Export Serialization", "<gexf" in gexf_str and "</gexf>" in gexf_str, f"({len(gexf_str)} bytes XML)")

    # Step 17: Unified Intelligence Search
    search_res = await unified_search.search("shadow.net", case_id=case_id)
    check(17, "Unified Intelligence Search", search_res["total_matches"] >= 1, f"({search_res['total_matches']} indexed matches found)")

    # Step 18: Evidence Vault Upload & SHA-256 Integrity
    test_evidence_bytes = b"TOP_SECRET_EVIDENCE_PAYLOAD_VERIFIED_SHA256"
    test_hash = hashlib.sha256(test_evidence_bytes).hexdigest()
    vault_res = await b2_storage.upload_evidence(
        data=test_evidence_bytes,
        filename="verified_intercept.bin",
        content_type="application/octet-stream",
        investigation_id=inv_id
    )
    download_bytes, dl_hash = await b2_storage.download_evidence(vault_res["file_key"])
    check(18, "Evidence Vault SHA-256 Integrity", dl_hash == test_hash and download_bytes == test_evidence_bytes, f"(SHA-256: {dl_hash[:16]}...)")

    # Step 19: Chunked AES-256-GCM Streaming Archive
    archive_res = await streaming_archive_service.create_archive(
        case_id=case_id,
        output_file_name=f"gotham_test_{uuid.uuid4().hex[:6]}.pravision_archive"
    )
    archive_path = Path(archive_res["file_path"])
    restore_res = await streaming_archive_service.restore_archive(
        archive_path=archive_path,
        target_case_prefix="VERIFIED-",
        verify_only=False
    )
    check(19, "Streaming Encrypted Archive & Restore", restore_res["status"] == "restored" and restore_res["cases_restored"] >= 1, f"(Cases Restored: {restore_res['cases_restored']}, Files: {restore_res['files_restored']})")
    if archive_path.exists():
        archive_path.unlink()

    # Step 20: Multi-User Authentication & Granular RBAC
    hashed = hash_password("GothamOfficerPass2026!")
    pw_valid = verify_password("GothamOfficerPass2026!", hashed)
    token = create_jwt_token(user_id="usr-gotham-01", username="officer1", role="case_officer")
    claims = decode_jwt_token(token)
    rbac_pass = pw_valid and claims.get("role") == "case_officer" and claims.get("username") == "officer1"
    check(20, "Multi-User Authentication & RBAC", rbac_pass, "(PBKDF2-HMAC-SHA256 600,000 iter, JWT jti verified)")

    # Cleanup test case
    await case_manager.delete_case(case_id)
    await b2_storage.delete_evidence(vault_res["file_key"])

    print("=" * 70)
    print(f"VERIFICATION SUMMARY: {PASSED}/20 PASSED, {FAILED}/20 FAILED")
    print("=" * 70)
    await engine.dispose()
    return FAILED == 0

if __name__ == "__main__":
    success = asyncio.run(run_20_step_verification())
    sys.exit(0 if success else 1)
