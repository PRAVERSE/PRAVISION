import asyncio
import os
import sys
import uuid
import time
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, check_db_health, async_session_maker
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from sqlalchemy import select

async def run_single_concurrent_investigation(idx: int):
    """Executes a full lifecycle investigation concurrently."""
    t0 = time.perf_counter()
    target_ip = f"10.{idx}.0.1"
    target_domain = f"target-{idx}.corp"
    
    # 1. Create dedicated case
    case = await case_manager.create_case(
        title=f"Concurrent Case {idx} - {uuid.uuid4().hex[:6]}",
        description=f"Concurrency benchmark workload worker {idx}",
        created_by=f"Worker_{idx}",
        classification="RESTRICTED",
        tags=["concurrent_test", f"worker_{idx}"]
    )
    case_id = case["id"]

    # 2. Upload dedicated evidence
    evidence_payload = f"EVIDENCE_LOG_FOR_WORKER_{idx}_{uuid.uuid4().hex}".encode("utf-8")
    expected_hash = hashlib.sha256(evidence_payload).hexdigest()
    inv_id = f"inv_conc_{idx}_{uuid.uuid4().hex[:6]}"
    
    up_res = await b2_storage.upload_evidence(
        data=evidence_payload,
        filename=f"evidence_w{idx}.log",
        content_type="text/plain",
        investigation_id=inv_id
    )
    file_key = up_res["file_key"]
    assert up_res["file_hash"] == expected_hash

    # 3. Formulate entities, relationships, findings
    findings = [
        EvidenceFinding(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            entity_type=EntityType.IP_ADDRESS,
            entity_value=target_ip,
            source_name="Concurrency Engine",
            evidence_description=f"Observed endpoint worker {idx}",
            confidence=ConfidenceLevel.HIGH,
            raw_payload={"file_key": file_key, "file_hash": expected_hash, "worker_idx": idx}
        )
    ]
    graph_nodes = [
        {"id": f"node_ip_{idx}", "label": target_ip, "type": "ip_address", "confidence": "high"},
        {"id": f"node_dom_{idx}", "label": target_domain, "type": "domain", "confidence": "high"}
    ]
    graph_edges = [
        {"source": target_ip, "target": target_domain, "relationship": "RESOLVES_TO", "confidence": "high"}
    ]

    # 4. Save to Case
    saved = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input=target_ip,
        root_type="ip_address",
        mode="mode_5_domain",
        findings=findings,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )
    assert saved["status"] == "saved"

    # 5. Query back and verify isolation (no cross-contamination)
    retrieved = await case_manager.get_case(case_id)
    assert retrieved is not None
    assert retrieved["entities_count"] == 2
    assert retrieved["evidence_count"] == 1
    assert len(retrieved["investigations"]) == 1

    # 6. Verify evidence download from S3
    dl_data, dl_hash = await b2_storage.download_evidence(file_key)
    assert dl_hash == expected_hash
    assert dl_data == evidence_payload

    # 7. Clean up
    deleted = await case_manager.delete_case(case_id, delete_evidence_files=True)
    assert deleted is True

    t1 = time.perf_counter()
    duration_ms = (t1 - t0) * 1000
    return {
        "worker_idx": idx,
        "case_id": case_id,
        "inv_id": inv_id,
        "duration_ms": duration_ms,
        "success": True
    }

async def run_concurrency_batch(concurrency_level: int):
    print("\n" + "-" * 70)
    print(f"CONCURRENCY LEVEL: {concurrency_level} PARALLEL INVESTIGATIONS")
    print("-" * 70)

    t0 = time.perf_counter()
    tasks = [run_single_concurrent_investigation(i) for i in range(concurrency_level)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time_ms = (time.perf_counter() - t0) * 1000

    failures = [r for r in results if isinstance(r, Exception)]
    successes = [r for r in results if not isinstance(r, Exception)]

    print(f"Results for N={concurrency_level} Concurrency:")
    print(f"  • Total Batch Execution Time: {total_time_ms:.2f} ms")
    print(f"  • Successful Investigations:   {len(successes)} / {concurrency_level}")
    print(f"  • Failed Investigations:       {len(failures)} / {concurrency_level}")

    if failures:
        for idx, f in enumerate(failures):
            print(f"    [FAIL] Worker error: {f}")
        assert False, f"{len(failures)} workers failed during concurrency test!"

    durations = [s["duration_ms"] for s in successes]
    print(f"  • Worker Latency Min:         {min(durations):.2f} ms")
    print(f"  • Worker Latency Mean:        {sum(durations)/len(durations):.2f} ms")
    print(f"  • Worker Latency Max:         {max(durations):.2f} ms")
    print(f"  • Effective Throughput:       {len(successes) / (total_time_ms / 1000):.2f} investigations/sec")
    print(f"[PASS] Concurrency Level {concurrency_level} completed with 100% data isolation and zero leakage.")

async def main():
    print("=" * 80)
    print("PRAVISION PHASE 2.3 — CONCURRENT INVESTIGATION SCALABILITY AUDIT")
    print("=" * 80)
    await init_db()

    # Test 5 concurrent investigations
    await run_concurrency_batch(5)

    # Test 10 concurrent investigations
    await run_concurrency_batch(10)

    print("\n" + "=" * 80)
    print("ALL CONCURRENCY SCALABILITY BENCHMARKS PASSED COMPLETELY.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

