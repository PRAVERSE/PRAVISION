import asyncio
import os
import sys
import time
import uuid
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.backup_system import backup_system
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel

async def test_backup_restore_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.4 — CASE DOSSIER & EVIDENCE BACKUP/RESTORE VERIFICATION")
    print("=" * 80)
    start_time = time.time()

    await init_db()

    # 1. Provision an isolated test case with real evidence
    case_title = f"Phase 2.4 Backup Verification — {uuid.uuid4().hex[:6]}"
    case = await case_manager.create_case(
        title=case_title,
        description="End-to-end verification of dossier & actual evidence file backup",
        created_by="Principal Reliability Engineer",
        classification="SECRET",
        tags=["phase_2_4", "backup_test"]
    )
    case_id = case["id"]
    print(f"Created Test Case: {case_id} ({case['case_number']})")

    # Upload real evidence file to object storage
    raw_payload = b"PRAVISION_PHASE_2_4_EVIDENCE_PAYLOAD_CONFIDENTIAL_VERIFICATION"
    expected_hash = hashlib.sha256(raw_payload).hexdigest()
    up_res = await b2_storage.upload_evidence(
        data=raw_payload,
        filename="classified_doc.bin",
        content_type="application/octet-stream"
    )
    b2_file_key = up_res["file_key"]
    print(f"Uploaded Test Evidence to S3: Key={b2_file_key}, SHA-256={expected_hash}")

    # Attach investigation, entities, relationships, and evidence to case
    inv_id = f"inv_{uuid.uuid4().hex[:8]}"
    sample_finding = EvidenceFinding(
        investigation_id=inv_id,
        entity_type=EntityType.EMAIL,
        entity_value="classified.agent@pravision.local",
        source_name="Neon Backup Engine",
        evidence_description="Verified backup test finding #7741",
        confidence=ConfidenceLevel.CORROBORATED
    )
    sample_nodes = [
        {"id": "node_email_1", "label": "classified.agent@pravision.local", "type": "email", "confidence": "high"},
        {"id": "node_domain_1", "label": "pravision.local", "type": "domain", "confidence": "high"}
    ]
    sample_edges = [
        {"source": "node_email_1", "target": "node_domain_1", "type": "belongs_to", "confidence": "high"}
    ]

    saved_inv = await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=inv_id,
        root_input="classified.agent@pravision.local",
        root_type="email",
        mode="email_intel",
        findings=[sample_finding],
        graph_nodes=sample_nodes,
        graph_edges=sample_edges
    )
    # Manually associate the evidence file record with this case
    await case_manager.attach_evidence(
        case_id=case_id,
        investigation_id=inv_id,
        entity_id=None,
        connector_name="evidence_vault",
        file_key=b2_file_key,
        file_hash=expected_hash,
        file_mime_type="application/octet-stream",
        file_size=len(raw_payload)
    )
    print("Associated investigation, entities, relationships, and real evidence record to case.")

    # 2. Execute automated backup
    print("\n" + "-" * 70)
    print("STEP 2: Creating Encrypted Backup Package with Actual Evidence File...")
    print("-" * 70)
    bkp_res = await backup_system.create_backup(case_id=case_id, sync_to_cloud=False)
    backup_id = bkp_res["backup_id"]
    print("Backup Result:", bkp_res)
    assert bkp_res["status"] == "verified"
    assert bkp_res["total_cases"] == 1
    assert bkp_res["total_files"] >= 1
    assert bkp_res["size_bytes"] > 0
    print(f"[PASS] Backup created and verified: {backup_id} ({bkp_res['size_bytes']} bytes).")

    # 3. Read encrypted backup archive
    backup_bytes = backup_system.get_backup_bytes(backup_id)
    assert backup_bytes is not None
    assert backup_bytes.startswith(b"PVBKP\x02")
    print(f"[PASS] Backup container magic header verified (AES-256-GCM container).")

    # 4. Verify-only restoration pass
    print("\n" + "-" * 70)
    print("STEP 3: Testing Dry-Run Verification without Database Writes...")
    print("-" * 70)
    dry_run = await backup_system.restore_backup(backup_bytes, verify_only=True)
    assert dry_run["status"] == "verified"
    assert dry_run["total_cases"] == 1
    assert dry_run["total_files"] >= 1
    print(f"[PASS] Dry-run verification passed: Package SHA-256={dry_run['package_sha256'][:16]}...")

    # 5. Full restoration with prefix into isolated target
    print("\n" + "-" * 70)
    print("STEP 4: Executing Full Restoration into Isolated Target Case...")
    print("-" * 70)
    restore_res = await backup_system.restore_backup(
        backup_bytes=backup_bytes,
        target_case_prefix="RESTORED_",
        verify_only=False
    )
    print("Restoration Result:", restore_res)
    assert restore_res["status"] == "restored"
    assert restore_res["cases_restored"] == 1
    assert restore_res["files_restored"] >= 1
    print("[PASS] Full restoration completed successfully.")

    # 6. Verify restored case content in database
    all_cases = await case_manager.list_cases()
    restored_case = next((c for c in all_cases if c["title"] == f"RESTORED_{case_title}"), None)
    assert restored_case is not None, "Restored case not found in database!"
    print(f"Verified Restored Case in DB: ID={restored_case['id']}, Title={restored_case['title']}")

    # 7. Cleanup both original and restored test cases and S3 evidence
    print("\n" + "-" * 70)
    print("STEP 5: Post-Test Cleanup...")
    print("-" * 70)
    await case_manager.delete_case(case_id)
    await case_manager.delete_case(restored_case["id"])
    await b2_storage.delete_evidence(b2_file_key)
    print("[PASS] All temporary test cases, restored records, and S3 objects safely deleted.")

    duration = time.time() - start_time
    print(f"\nExecution Duration: {duration:.2f}s")
    print("=" * 80)
    print("ALL CASE DOSSIER & EVIDENCE BACKUP/RESTORE TESTS PASSED 100%.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_backup_restore_suite())

