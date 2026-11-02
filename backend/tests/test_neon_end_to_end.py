import asyncio
import os
import sys
import uuid
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, check_db_health, IS_POSTGRES, async_session_maker
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

async def test_neon_full_stack():
    print("=" * 80)
    print("PRAVISION // NEON CLOUD SERVICES END-TO-END VERIFICATION")
    print("=" * 80)

    # 1. Initialize schema in Neon Lakebase Postgres
    print("\n[STEP 1] Initializing schema on Neon Lakebase Postgres...")
    await init_db()
    health = await check_db_health()
    print("Neon Database Health Check:", health)
    assert health["status"] == "healthy", f"Database unhealthy: {health}"
    assert "Neon" in health["backend"], f"Backend not Neon: {health['backend']}"
    assert health["is_postgres"] is True
    print(f"Verified: Neon Lakebase Postgres is healthy (Latency: {health['latency_ms']}ms)")

    # 2. Check Neon Object Storage Status
    print("\n[STEP 2] Verifying Neon Object Storage connection...")
    storage_status = b2_storage.get_status()
    print("Neon Object Storage Status:", storage_status)
    assert storage_status["cloud_enabled"] is True
    assert "Neon" in storage_status["storage_mode"]
    assert storage_status["bucket"] == "pravision-evidence"
    print(f"Verified: Connected to Neon Object Storage bucket '{storage_status['bucket']}' at {storage_status['endpoint']}")

    # 3. Create Case Dossier in Neon Postgres
    print("\n[STEP 3] Creating Case Dossier in Neon Postgres...")
    case_title = f"Operation Neon Cloud Integration - {uuid.uuid4().hex[:6]}"
    case = await case_manager.create_case(
        title=case_title,
        description="End-to-end integration test of Neon Lakebase Postgres & Object Storage",
        created_by="Neon Cloud Engineer",
        classification="SECRET",
        tags=["neon", "lakebase_postgres", "object_storage"]
    )
    case_id = case["id"]
    print(f"Created Case in Neon: ID={case_id}, Number={case['case_number']}")
    assert case_id is not None

    # 4. Upload Evidence to Neon Object Storage
    print("\n[STEP 4] Uploading evidence file to Neon Object Storage bucket...")
    evidence_payload = b"CRITICAL OSINT TELEMETRY // NEON CLOUD STORAGE OBJECT // " + uuid.uuid4().bytes
    expected_hash = hashlib.sha256(evidence_payload).hexdigest()
    
    upload_res = await b2_storage.upload_evidence(
        data=evidence_payload,
        filename="neon_intercept_payload.bin",
        content_type="application/octet-stream",
        investigation_id=case_id
    )
    print("Upload Result from Neon S3:", upload_res)
    assert upload_res["storage_backend"] == "neon_cloud"
    assert upload_res["file_hash"] == expected_hash
    file_key = upload_res["file_key"]
    print(f"Verified: Uploaded to Neon bucket with SHA-256: {expected_hash}")

    # 5. Download and Validate Bit-for-Bit Integrity from Neon
    print("\n[STEP 5] Downloading evidence from Neon S3 and validating SHA-256...")
    downloaded_bytes, dl_hash = await b2_storage.download_evidence(file_key)
    assert dl_hash == expected_hash
    assert downloaded_bytes == evidence_payload
    print(f"Verified: Bit-for-bit SHA-256 checksum matched ({dl_hash})")

    # 6. Save Investigation with Relational Entities & Evidence into Neon Postgres
    print("\n[STEP 6] Saving Investigation with Entities and Neon Evidence Key...")
    inv_id = f"inv_neon_{uuid.uuid4().hex[:8]}"
    sample_finding = EvidenceFinding(
        id=str(uuid.uuid4()),
        investigation_id=inv_id,
        entity_type=EntityType.DOMAIN,
        entity_value="neon.tech",
        source_name="Neon Lakebase Engine",
        evidence_description="Cloud database provider infrastructure host",
        confidence=ConfidenceLevel.CORROBORATED,
        raw_payload={"file_key": file_key, "sha256": expected_hash}
    )
    graph_nodes = [
        {"id": "node_neon_1", "label": "neon.tech", "type": "domain", "confidence": "high"},
        {"id": "node_ip_1", "label": "13.251.17.193", "type": "ip_address", "confidence": "high"}
    ]
    graph_edges = [
        {"source": "neon.tech", "target": "13.251.17.193", "relationship": "RESOLVES_TO", "confidence": "high"}
    ]

    saved_inv = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input="neon.tech",
        root_type="domain",
        mode="mode_5_website",
        findings=[sample_finding],
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )
    print("Saved Investigation into Neon Postgres:", saved_inv)
    assert saved_inv["status"] == "saved"

    # 7. Query back Case Dossier from Neon Postgres
    print("\n[STEP 7] Querying back Case Dossier from Neon Postgres...")
    queried_case = await case_manager.get_case(case_id)
    print(f"Queried Case: Entities={queried_case['entities_count']}, Evidence={queried_case['evidence_count']}, Investigations={len(queried_case['investigations'])}")
    assert queried_case["entities_count"] == 2
    assert queried_case["evidence_count"] == 1
    assert len(queried_case["investigations"]) == 1

    # 8. Clean up test evidence and case
    print("\n[STEP 8] Cleaning up test evidence and case...")
    del_evidence_ok = await b2_storage.delete_evidence(file_key)
    print(f"Deleted test object from Neon Object Storage: {del_evidence_ok}")
    assert del_evidence_ok is True

    del_case_ok = await case_manager.delete_case(case_id)
    print(f"Deleted test case from Neon Lakebase Postgres: {del_case_ok}")
    assert del_case_ok is True

    print("\n" + "=" * 80)
    print("ALL NEON CLOUD SERVICES VERIFIED END-TO-END WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_neon_full_stack())

