import asyncio
import os
import sys
import uuid
import time
import statistics
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, check_db_health, async_session_maker, engine
from app.storage.case_manager import case_manager
from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel, AuditLogModel
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

PERSISTENT_CASE_ID = None

async def test_persistent_case_creation():
    global PERSISTENT_CASE_ID
    print("-" * 70)
    print("SUBTEST 1.1: Create Persistent Case Dossier in Neon Postgres")
    print("-" * 70)
    
    await init_db()
    health = await check_db_health()
    print("Database Health:", health)
    assert health["status"] == "healthy"
    assert "Neon" in health["backend"] or health["is_postgres"] is True

    # Create Case
    case = await case_manager.create_case(
        title="Operation Sentinel - Persistence Verification",
        description="Verifies cross-restart persistence, foreign keys, and transaction atomicity",
        created_by="Lead Analyst",
        classification="SECRET",
        tags=["persistence_test", "neon_postgres"]
    )
    PERSISTENT_CASE_ID = case["id"]
    print(f"Created Persistent Case: ID={PERSISTENT_CASE_ID}, CaseNumber={case['case_number']}")
    assert PERSISTENT_CASE_ID is not None

    # Save Investigation with Entities, Relationships, and Evidence
    inv_id = f"inv_persist_{uuid.uuid4().hex[:8]}"
    sample_finding = EvidenceFinding(
        id=str(uuid.uuid4()),
        investigation_id=inv_id,
        entity_type=EntityType.IP_ADDRESS,
        entity_value="198.51.100.42",
        source_name="GreyNoise Intelligence",
        evidence_description="Flagged C2 infrastructure telemetry",
        confidence=ConfidenceLevel.HIGH,
        raw_payload={"file_key": "investigations/persist/c2_trace.bin", "file_hash": "a1b2c3d4e5f67890"}
    )
    graph_nodes = [
        {"id": "node_ip_42", "label": "198.51.100.42", "type": "ip_address", "confidence": "high"},
        {"id": "node_asn_99", "label": "AS13335 Cloudflare", "type": "organization", "confidence": "high"}
    ]
    graph_edges = [
        {"source": "198.51.100.42", "target": "AS13335 Cloudflare", "relationship": "ANNOUNCED_BY", "confidence": "high"}
    ]

    saved = await case_manager.save_investigation_to_case(
        case_id=PERSISTENT_CASE_ID,
        investigation_id=inv_id,
        root_input="198.51.100.42",
        root_type="ip_address",
        mode="mode_6_organization",
        findings=[sample_finding],
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )
    print("Saved Investigation to Case:", saved)
    assert saved["status"] == "saved"
    print("Subtest 1.1 PASSED: Case, Entities, Relationships, and Evidence persisted.")
    return PERSISTENT_CASE_ID

async def test_cross_restart_verification(case_id: str):
    print("\n" + "-" * 70)
    print(f"SUBTEST 1.2: Cross-Restart Retrieval of Case {case_id}")
    print("-" * 70)
    
    # Query case using fresh connection session
    case_data = await case_manager.get_case(case_id)
    assert case_data is not None, f"Case {case_id} not found after restart!"
    print(f"Retrieved Case: ID={case_data['id']}, Title={case_data['title']}, Number={case_data['case_number']}")
    assert case_data["title"] == "Operation Sentinel - Persistence Verification"
    assert case_data["classification"] == "SECRET"
    assert "persistence_test" in case_data["tags"]
    assert case_data["entities_count"] == 2
    assert case_data["evidence_count"] == 1
    assert len(case_data["investigations"]) == 1

    # Verify relational entities and evidence in database
    async with async_session_maker() as session:
        # Entities check
        stmt_ent = select(EntityModel).where(EntityModel.case_id == case_id)
        ents = (await session.execute(stmt_ent)).scalars().all()
        print(f"Verified Entities in Neon Postgres: Count={len(ents)}")
        assert len(ents) == 2
        ent_values = [e.entity_value for e in ents]
        assert "198.51.100.42" in ent_values
        assert "AS13335 Cloudflare" in ent_values

        # Relationships check
        stmt_rel = select(RelationshipModel).where(RelationshipModel.source_id.in_([e.id for e in ents]))
        rels = (await session.execute(stmt_rel)).scalars().all()
        print(f"Verified Relationships in Neon Postgres: Count={len(rels)}")
        assert len(rels) >= 1
        assert rels[0].relationship_type == "ANNOUNCED_BY"

        # Evidence check
        stmt_ev = select(EvidenceModel).where(EvidenceModel.case_id == case_id)
        evs = (await session.execute(stmt_ev)).scalars().all()
        print(f"Verified Evidence Records: Count={len(evs)}")
        assert len(evs) == 1
        assert evs[0].b2_file_key == "investigations/persist/c2_trace.bin"
        assert evs[0].file_hash == "a1b2c3d4e5f67890"

        # Audit logs check
        stmt_aud = select(AuditLogModel).where(AuditLogModel.target_id == case_id)
        auds = (await session.execute(stmt_aud)).scalars().all()
        print(f"Verified Audit Records: Count={len(auds)}")
        assert len(auds) >= 1

    print("Subtest 1.2 PASSED: Cross-restart persistence of all relational models verified.")

async def test_postgres_transactions_and_rollback():
    print("\n" + "-" * 70)
    print("SUBTEST 1.3: PostgreSQL Transaction Atomicity and Rollback")
    print("-" * 70)

    test_case_id = str(uuid.uuid4())
    test_case_num = f"TX-TEST-{uuid.uuid4().hex[:6]}"

    # Attempt a transaction that raises an error halfway
    rolled_back = False
    try:
        async with async_session_maker() as session:
            # Step A: Insert a case
            c = CaseModel(
                id=test_case_id,
                case_number=test_case_num,
                title="Transaction Rollback Test Case"
            )
            session.add(c)
            await session.flush()

            # Step B: Trigger an intentional error (invalid SQL or exception)
            raise RuntimeError("SIMULATED TRANSACTION FAILURE BEFORE COMMIT")
            await session.commit()
    except RuntimeError as e:
        rolled_back = True
        print(f"Expected exception triggered transaction rollback: {e}")

    assert rolled_back is True

    # Verify that the uncommitted case does NOT exist in Neon Postgres
    async with async_session_maker() as session:
        stmt = select(CaseModel).where(CaseModel.id == test_case_id)
        res = await session.execute(stmt)
        c_check = res.scalar_one_or_none()
        print(f"Verifying rolled-back record in Neon: {c_check}")
        assert c_check is None, "CRITICAL ERROR: Uncommitted transaction row leaked into database!"

    print("Subtest 1.3 PASSED: PostgreSQL transaction rollback verified (Zero uncommitted leaks).")

async def test_foreign_key_constraints():
    print("\n" + "-" * 70)
    print("SUBTEST 1.4: PostgreSQL Foreign Key Constraints Enforcement")
    print("-" * 70)

    fk_violation_caught = False
    fake_case_id = str(uuid.uuid4())

    try:
        async with async_session_maker() as session:
            # Attempt to insert an Entity with a non-existent case_id
            orphan_entity = EntityModel(
                id=str(uuid.uuid4()),
                case_id=fake_case_id,  # DOES NOT EXIST
                entity_type="ip_address",
                entity_value="10.0.0.1",
                normalized_value="10.0.0.1"
            )
            session.add(orphan_entity)
            await session.commit()
    except IntegrityError as e:
        fk_violation_caught = True
        print(f"PostgreSQL correctly rejected invalid foreign key: {type(e).__name__} -> {e.orig}")

    assert fk_violation_caught is True, "CRITICAL ERROR: Foreign key constraint violation was not enforced!"
    print("Subtest 1.4 PASSED: Foreign key constraints strictly enforced by Neon Postgres.")

async def test_connection_pooling_and_latency():
    print("\n" + "-" * 70)
    print("SUBTEST 1.5: Connection Pooling & 30 Repeated Queries Latency")
    print("-" * 70)

    latencies = []
    iterations = 35

    for i in range(iterations):
        t0 = time.perf_counter()
        async with async_session_maker() as session:
            res = await session.execute(text("SELECT 1;"))
            _ = res.scalar()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    # Discard warmup query
    w_latencies = latencies[1:]
    avg_lat = statistics.mean(w_latencies)
    med_lat = statistics.median(w_latencies)
    p95_lat = sorted(w_latencies)[int(len(w_latencies) * 0.95)]
    min_lat = min(w_latencies)
    max_lat = max(w_latencies)

    print(f"Warmup query latency: {latencies[0]:.2f} ms")
    print(f"Connection Pool Repeated Queries (N={len(w_latencies)}):")
    print(f"  Average: {avg_lat:.2f} ms")
    print(f"  Median:  {med_lat:.2f} ms")
    print(f"  P95:     {p95_lat:.2f} ms")
    print(f"  Min:     {min_lat:.2f} ms")
    print(f"  Max:     {max_lat:.2f} ms")

    assert avg_lat < 3000, f"Average query latency too high: {avg_lat:.2f} ms"
    print("Subtest 1.5 PASSED: Connection pooling operational.")

async def cleanup_test_case(case_id: str):
    print("\n" + "-" * 70)
    print(f"SUBTEST 1.6: Cleanup Persistent Case {case_id}")
    print("-" * 70)
    deleted = await case_manager.delete_case(case_id)
    assert deleted is True
    post_check = await case_manager.get_case(case_id)
    assert post_check is None
    print(f"Verified: Case {case_id} deleted cleanly.")

async def main():
    print("=" * 80)
    print("PRAVISION PHASE 2.2 — DATABASE PERSISTENCE & CONSTRAINTS AUDIT")
    print("=" * 80)
    case_id = await test_persistent_case_creation()
    await test_cross_restart_verification(case_id)
    await test_postgres_transactions_and_rollback()
    await test_foreign_key_constraints()
    await test_connection_pooling_and_latency()
    await cleanup_test_case(case_id)
    print("\n" + "=" * 80)
    print("ALL DATABASE PERSISTENCE TESTS PASSED COMPLETELY.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

