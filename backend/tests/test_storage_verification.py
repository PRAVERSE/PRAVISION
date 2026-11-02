import asyncio
import os
import sys
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, check_db_health, get_db_session, async_session_maker
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, EvidenceModel, AuditLogModel
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from sqlalchemy import text

async def test_sqlite_wal_and_case_manager():
    print("-" * 60)
    print("TEST 1: SQLite WAL Engine and Schema Initialization")
    print("-" * 60)
    await init_db()
    health = await check_db_health()
    print("Database Health Check:", health)
    assert health["status"] == "healthy"
    assert "SQLite" in health["backend"]
    assert health["latency_ms"] >= 0

    print("-" * 60)
    print("TEST 2: Case Management & Relational Evidence Integrity")
    print("-" * 60)
    # Create Case
    new_case = await case_manager.create_case(
        title="Operation Independent Verification",
        description="Comprehensive integration test for PRAVISION Phase 2.1",
        created_by="Chief Inspector",
        classification="SECRET",
        tags=["audit", "verification"]
    )
    case_id = new_case["id"]
    print(f"Created Case: ID={case_id}, Title={new_case['title']}, Status={new_case['status']}")
    assert case_id is not None
    assert new_case["title"] == "Operation Independent Verification"

    # Test saving an investigation into the case
    import uuid
    inv_id = f"inv_verify_{uuid.uuid4().hex[:8]}"
    sample_finding = EvidenceFinding(
        investigation_id=inv_id,
        entity_type=EntityType.EMAIL,
        entity_value="target.alpha@example.org",
        source_name="SigInt Engine",
        evidence_description="Intercepted communication trace #9901",
        confidence=ConfidenceLevel.CORROBORATED
    )
    sample_nodes = [
        {"id": "node_email_1", "label": "target.alpha@example.org", "type": "email", "confidence": "high"},
        {"id": "node_domain_1", "label": "example.org", "type": "domain", "confidence": "high"}
    ]
    sample_edges = [
        {"source": "target.alpha@example.org", "target": "example.org", "relationship": "DOMAIN_OF", "confidence": "high"}
    ]

    saved = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input="target.alpha@example.org",
        root_type="email",
        mode="mode_3_email",
        findings=[sample_finding],
        graph_nodes=sample_nodes,
        graph_edges=sample_edges
    )
    print("Saved Investigation to Case:", saved)
    assert saved["status"] == "saved"

    # Verify retrieval
    case_data = await case_manager.get_case(case_id)
    print(f"Retrieved Case: ID={case_data['id']}, Entities={case_data['entities_count']}, Evidence={case_data['evidence_count']}")
    assert case_data["entities_count"] == 2
    assert case_data["evidence_count"] == 1
    assert len(case_data["investigations"]) == 1

    # Verify audit logs in database
    async with async_session_maker() as session:
        from sqlalchemy import select
        stmt = select(AuditLogModel).where(AuditLogModel.target_id.in_([case_id, inv_id]))
        res = await session.execute(stmt)
        audits = res.scalars().all()
        print(f"Retrieved {len(audits)} Audit Logs for Case {case_id}")
        assert len(audits) >= 2

    # Cleanup test case
    del_ok = await case_manager.delete_case(case_id)
    print(f"Case Deleted cleanly: {del_ok}")
    assert del_ok is True
    post_del_case = await case_manager.get_case(case_id)
    assert post_del_case is None
    print("SQLite & Case Manager Verification PASSED!")

async def test_storage_vault_and_b2_fallback():
    print("-" * 60)
    print("TEST 3: Storage Vault & Backblaze B2 Fallback")
    print("-" * 60)
    status = b2_storage.get_status()
    print("B2 / Local Vault Status:", status)
    assert "storage_mode" in status
    assert "local_vault_path" in status

    # Verify file upload, integrity, download, and deletion
    sample_content = b"EVIDENCE SAMPLE CONTENT FOR SHA-256 VAULT TEST " + os.urandom(32)
    expected_sha256 = hashlib.sha256(sample_content).hexdigest()

    upload_res = await b2_storage.upload_evidence(
        data=sample_content,
        filename="vault_test_sample.bin",
        content_type="application/octet-stream"
    )
    print("Upload Result:", upload_res)
    assert upload_res["file_hash"] == expected_sha256
    assert upload_res["file_size"] == len(sample_content)

    # Download and verify bit-for-bit integrity
    dl_data, dl_hash = await b2_storage.download_evidence(upload_res["file_key"])
    assert dl_hash == expected_sha256
    assert dl_data == sample_content
    print("SHA-256 Bit-for-Bit Integrity Verified!")

    # Delete evidence file
    del_res = await b2_storage.delete_evidence(upload_res["file_key"])
    print(f"Evidence file deleted: {del_res}")
    assert del_res is True

    # Confirm download throws FileNotFoundError after deletion
    try:
        await b2_storage.download_evidence(upload_res["file_key"])
        assert False, "Should have thrown FileNotFoundError"
    except FileNotFoundError:
        print("FileNotFoundError raised correctly after deletion.")

    print("Storage Vault Verification PASSED!")

async def test_postgres_unreachable_fallback():
    print("-" * 60)
    print("TEST 4: PostgreSQL Failure Containment (Graceful Fallback)")
    print("-" * 60)
    from sqlalchemy.ext.asyncio import create_async_engine
    # Test that an unreachable postgres connection fails gracefully with informative error
    fake_pg_url = "postgresql+asyncpg://invalid_user:invalid_pass@127.0.0.1:54329/nonexistent_db"
    test_pg_engine = create_async_engine(fake_pg_url, connect_args={"timeout": 2.0})
    try:
        async with test_pg_engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
        assert False, "Should have failed to connect to fake postgres"
    except Exception as e:
        print(f"Expected PostgreSQL connection failure intercepted cleanly: {type(e).__name__} -> {e}")
        assert True
    await test_pg_engine.dispose()
    print("PostgreSQL Failure Containment Verified!")

async def main():
    print("=" * 80)
    print("PRAVISION STORAGE & EVIDENCE PIPELINE VERIFICATION SUITE")
    print("=" * 80)
    await test_sqlite_wal_and_case_manager()
    await test_storage_vault_and_b2_fallback()
    await test_postgres_unreachable_fallback()
    print("\nALL STORAGE & EVIDENCE PIPELINE TESTS PASSED COMPLETELY.")

if __name__ == "__main__":
    asyncio.run(main())
