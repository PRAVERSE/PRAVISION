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
from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from sqlalchemy import text, select

async def run_database_performance_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.3 — DATABASE PERFORMANCE AUDIT & BENCHMARKS")
    print("=" * 80)

    # 1. Cold Connection vs Warm Pool Connection Latency
    print("\n" + "-" * 70)
    print("METRIC 1: Cold Connection vs Warm Pooled Query Latency")
    print("-" * 70)
    
    t0_init = time.perf_counter()
    await init_db()
    cold_connect_ms = (time.perf_counter() - t0_init) * 1000
    print(f"Cold Initialization & Connection Ping: {cold_connect_ms:.2f} ms")

    # 35 Repeated Pooled Queries
    latencies = []
    iterations = 35
    for i in range(iterations):
        t0 = time.perf_counter()
        async with async_session_maker() as session:
            res = await session.execute(text("SELECT 1;"))
            _ = res.scalar()
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000)

    warmup = latencies[0]
    eval_latencies = latencies[1:]
    avg_lat = statistics.mean(eval_latencies)
    med_lat = statistics.median(eval_latencies)
    p95_lat = sorted(eval_latencies)[int(len(eval_latencies) * 0.95)]
    min_lat = min(eval_latencies)
    max_lat = max(eval_latencies)
    stdev_lat = statistics.stdev(eval_latencies) if len(eval_latencies) > 1 else 0

    print(f"Warmup Query: {warmup:.2f} ms")
    print(f"Warm Pooled Queries (N={len(eval_latencies)}):")
    print(f"  • Min:    {min_lat:.2f} ms")
    print(f"  • Mean:   {avg_lat:.2f} ms")
    print(f"  • Median: {med_lat:.2f} ms")
    print(f"  • P95:    {p95_lat:.2f} ms")
    print(f"  • Max:    {max_lat:.2f} ms")
    print(f"  • StDev:  {stdev_lat:.2f} ms")

    # 2. Case Creation and Retrieval Latency
    print("\n" + "-" * 70)
    print("METRIC 2: Case Dossier Creation & Retrieval Latency")
    print("-" * 70)

    t0_create = time.perf_counter()
    case = await case_manager.create_case(
        title=f"Benchmark Case - {uuid.uuid4().hex[:6]}",
        description="Testing performance characteristics for Phase 2.3",
        created_by="PerfAnalyst",
        classification="CONFIDENTIAL",
        tags=["perf", "phase_2_3"]
    )
    case_create_ms = (time.perf_counter() - t0_create) * 1000
    case_id = case["id"]
    print(f"Case Creation Latency: {case_create_ms:.2f} ms (ID: {case_id})")

    t0_get = time.perf_counter()
    retrieved_case = await case_manager.get_case(case_id)
    case_get_ms = (time.perf_counter() - t0_get) * 1000
    print(f"Case Retrieval Latency (with eager child loads): {case_get_ms:.2f} ms")
    assert retrieved_case is not None

    # 3. Investigation, Entity, and Relationship Persistence Latency
    print("\n" + "-" * 70)
    print("METRIC 3: Investigation & Relational Graph Persistence Latency")
    print("-" * 70)

    inv_id = f"inv_bench_{uuid.uuid4().hex[:8]}"
    sample_findings = [
        EvidenceFinding(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            entity_type=EntityType.IP_ADDRESS,
            entity_value=f"198.51.100.{i}",
            source_name="GreyNoise",
            evidence_description="C2 endpoint observation",
            confidence=ConfidenceLevel.HIGH,
            raw_payload={"port": 443 + i, "sha256": f"dummyhash_{i}"}
        )
        for i in range(5)
    ]
    graph_nodes = [
        {"id": f"node_{i}", "label": f"198.51.100.{i}", "type": "ip_address", "confidence": "high"}
        for i in range(5)
    ]
    graph_edges = [
        {"source": f"198.51.100.{i}", "target": f"198.51.100.{i+1}", "relationship": "LATERAL_MOVE", "confidence": "high"}
        for i in range(4)
    ]

    t0_save = time.perf_counter()
    save_res = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input="198.51.100.0/24",
        root_type="ip_network",
        mode="mode_6_organization",
        findings=sample_findings,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )
    save_ms = (time.perf_counter() - t0_save) * 1000
    print(f"Relational Graph Persistence Latency (5 findings, 5 entities, 4 relationships): {save_ms:.2f} ms")

    # 4. Entity & Relationship Query Latency
    print("\n" + "-" * 70)
    print("METRIC 4: Entity & Relationship Query Latency")
    print("-" * 70)

    t0_q_ent = time.perf_counter()
    async with async_session_maker() as session:
        stmt_ent = select(EntityModel).where(EntityModel.case_id == case_id)
        ents = (await session.execute(stmt_ent)).scalars().all()
    query_ent_ms = (time.perf_counter() - t0_q_ent) * 1000
    print(f"Entity Query Latency: {query_ent_ms:.2f} ms (Count: {len(ents)})")

    t0_q_rel = time.perf_counter()
    async with async_session_maker() as session:
        stmt_rel = select(RelationshipModel).where(RelationshipModel.investigation_id == inv_id)
        rels = (await session.execute(stmt_rel)).scalars().all()
    query_rel_ms = (time.perf_counter() - t0_q_rel) * 1000
    print(f"Relationship Query Latency: {query_rel_ms:.2f} ms (Count: {len(rels)})")

    # 5. PostgreSQL EXPLAIN ANALYZE on Critical Queries
    print("\n" + "-" * 70)
    print("METRIC 5: PostgreSQL EXPLAIN ANALYZE on Core Queries")
    print("-" * 70)

    async with async_session_maker() as session:
        # Case lookup by case_number
        explain_case = await session.execute(text(
            f"EXPLAIN ANALYZE SELECT * FROM cases WHERE case_number = '{case['case_number']}';"
        ))
        print("EXPLAIN ANALYZE (cases by case_number):")
        for line in explain_case.scalars().all():
            print("  ", line)

        # Entity lookup by normalized_value
        explain_ent = await session.execute(text(
            f"EXPLAIN ANALYZE SELECT * FROM entities WHERE normalized_value = '198.51.100.0';"
        ))
        print("\nEXPLAIN ANALYZE (entities by normalized_value):")
        for line in explain_ent.scalars().all():
            print("  ", line)

        # Evidence lookup by file_hash
        explain_ev = await session.execute(text(
            f"EXPLAIN ANALYZE SELECT * FROM evidences WHERE file_hash = 'dummyhash_0';"
        ))
        print("\nEXPLAIN ANALYZE (evidences by file_hash):")
        for line in explain_ev.scalars().all():
            print("  ", line)

    # 6. Cleanup Benchmark Case
    await case_manager.delete_case(case_id)
    print(f"\nCleaned up benchmark case {case_id}.")

    print("\n" + "=" * 80)
    print("DATABASE PERFORMANCE AUDIT COMPLETED.")
    print("=" * 80)
    return {
        "cold_connect_ms": cold_connect_ms,
        "pooled_avg_ms": avg_lat,
        "pooled_p95_ms": p95_lat,
        "case_create_ms": case_create_ms,
        "case_get_ms": case_get_ms,
        "save_investigation_ms": save_ms,
        "query_ent_ms": query_ent_ms,
        "query_rel_ms": query_rel_ms,
    }

if __name__ == "__main__":
    asyncio.run(run_database_performance_suite())

