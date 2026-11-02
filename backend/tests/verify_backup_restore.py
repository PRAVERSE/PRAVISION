import asyncio
import os
import sys
import uuid
import json
import hashlib
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, check_db_health, async_session_maker
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.models_db import CaseModel, EntityModel, RelationshipModel, EvidenceModel
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from sqlalchemy import select

async def run_backup_and_disaster_recovery_audit():
    print("=" * 80)
    print("PRAVISION PHASE 2.3 — BACKUP & DISASTER RECOVERY AUDIT")
    print("=" * 80)
    await init_db()

    # 1. Create a Realistic Target Case with Relational Graph and Evidence
    print("\n" + "-" * 70)
    print("STEP 1: Create Case Dossier with Relational Graph & Evidence Artifact")
    print("-" * 70)

    case = await case_manager.create_case(
        title="Operation Chronos - Backup & Recovery Verification",
        description="Comprehensive case created to test disaster recovery export and re-import",
        created_by="Recovery Specialist",
        classification="SECRET",
        tags=["disaster_recovery", "neon_backup"]
    )
    original_case_id = case["id"]
    original_case_num = case["case_number"]
    print(f"Created Target Case: ID={original_case_id}, Number={original_case_num}")

    # Upload evidence file to Neon Object Storage
    test_evidence_bytes = b"PRAVISION_DISASTER_RECOVERY_IMMUTABLE_ARTIFACT_V1"
    evidence_sha = hashlib.sha256(test_evidence_bytes).hexdigest()
    inv_id = f"inv_recov_{uuid.uuid4().hex[:8]}"

    up_res = await b2_storage.upload_evidence(
        data=test_evidence_bytes,
        filename="mission_intel.raw",
        content_type="application/octet-stream",
        investigation_id=inv_id
    )
    file_key = up_res["file_key"]
    print(f"Uploaded Evidence to S3: Key={file_key}, SHA-256={evidence_sha[:16]}...")

    findings = [
        EvidenceFinding(
            id=str(uuid.uuid4()),
            investigation_id=inv_id,
            entity_type=EntityType.ORGANIZATION,
            entity_value="Syndicate Seven",
            source_name="OpenSanctions",
            evidence_description="Entity identified in offshore corporate registry",
            confidence=ConfidenceLevel.CORROBORATED,
            raw_payload={"file_key": file_key, "file_hash": evidence_sha, "size": len(test_evidence_bytes)}
        )
    ]
    graph_nodes = [
        {"id": "node_org_7", "label": "Syndicate Seven", "type": "organization", "confidence": "high"},
        {"id": "node_ip_99", "label": "203.0.113.77", "type": "ip_address", "confidence": "high"}
    ]
    graph_edges = [
        {"source": "Syndicate Seven", "target": "203.0.113.77", "relationship": "CONTROLS_INFRASTRUCTURE", "confidence": "high"}
    ]

    saved = await case_manager.save_investigation_to_case(
        case_id=original_case_id,
        investigation_id=inv_id,
        root_input="Syndicate Seven",
        root_type="organization",
        mode="mode_6_organization",
        findings=findings,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges
    )
    assert saved["status"] == "saved"
    print("Persisted investigation with entities and relationships.")

    # 2. Export Case Dossier as Cryptographic Backup Package
    print("\n" + "-" * 70)
    print("STEP 2: Export Case Dossier as Cryptographic Backup Package")
    print("-" * 70)

    backup_pkg = await case_manager.export_case_dossier(original_case_id)
    print(f"Exported Backup Package:")
    print(f"  • Format Version:    {backup_pkg['format_version']}")
    print(f"  • Exported At:       {backup_pkg['exported_at']}")
    print(f"  • Case Number:       {backup_pkg['case']['case_number']}")
    print(f"  • Investigations:    {len(backup_pkg['investigations'])}")
    print(f"  • Entities:          {len(backup_pkg['entities'])}")
    print(f"  • Relationships:     {len(backup_pkg['relationships'])}")
    print(f"  • Evidences:         {len(backup_pkg['evidences'])}")
    print(f"  • Audit Logs:        {len(backup_pkg['audit_logs'])}")
    print(f"  • SHA-256 Checksum:  {backup_pkg['checksum_sha256']}")
    assert backup_pkg["checksum_sha256"] is not None

    # Write backup file to disk in local temp vault
    backup_path = Path(backend_dir) / "evidence_vault" / f"backup_{original_case_num}.json"
    backup_path.write_text(json.dumps(backup_pkg, indent=2), encoding="utf-8")
    print(f"Saved local backup archive to: {backup_path.name}")

    # 3. Object Storage Evidence Backup (Offsite Archiving)
    print("\n" + "-" * 70)
    print("STEP 3: Object Storage Evidence Backup Verification")
    print("-" * 70)

    # Download evidence from cloud to local backup location
    backup_evidence_bytes, dl_sha = await b2_storage.download_evidence(file_key)
    assert dl_sha == evidence_sha
    assert backup_evidence_bytes == test_evidence_bytes
    print(f"Evidence artifact {file_key} successfully backed up and validated with SHA-256.")

    # 4. Simulate Disaster: Complete Deletion of the Case Dossier
    print("\n" + "-" * 70)
    print("STEP 4: Simulate Accidental Case Deletion (Disaster Trigger)")
    print("-" * 70)

    # Delete case from database (keeping the file in S3 or testing full restoration)
    deleted = await case_manager.delete_case(original_case_id, delete_evidence_files=False)
    assert deleted is True

    # Confirm case no longer exists in database
    disaster_check = await case_manager.get_case(original_case_id)
    assert disaster_check is None
    print(f"[VERIFIED] Case {original_case_id} completely expunged from Neon Lakebase Postgres.")

    # 5. Execute Disaster Recovery: Import Dossier from Backup Package
    print("\n" + "-" * 70)
    print("STEP 5: Execute Disaster Recovery from Backup Package")
    print("-" * 70)

    # Read backup from disk
    restored_pkg = json.loads(backup_path.read_text(encoding="utf-8"))
    import_res = await case_manager.import_case_dossier(restored_pkg, generate_new_ids=False)
    print("Restoration Import Result:", import_res)
    assert import_res["status"] == "imported"
    assert import_res["case_id"] == original_case_id

    # 6. Validate Fully Restored Case and Relational Integrity
    print("\n" + "-" * 70)
    print("STEP 6: Validate Restored Case Relational Graph & Evidence")
    print("-" * 70)

    restored_case = await case_manager.get_case(original_case_id)
    assert restored_case is not None
    assert restored_case["title"] == "Operation Chronos - Backup & Recovery Verification"
    assert restored_case["classification"] == "SECRET"
    assert restored_case["entities_count"] == 2
    assert restored_case["evidence_count"] == 1
    assert len(restored_case["investigations"]) == 1

    # Verify relationships restored
    async with async_session_maker() as session:
        stmt_rel = select(RelationshipModel).where(RelationshipModel.investigation_id == inv_id)
        rels = (await session.execute(stmt_rel)).scalars().all()
        assert len(rels) == 1
        assert rels[0].relationship_type == "CONTROLS_INFRASTRUCTURE"
        print(f"Verified Restored Relationship: {rels[0].relationship_type}")

    # Verify cloud evidence still accessible and matching
    s3_data, s3_sha = await b2_storage.download_evidence(file_key)
    assert s3_sha == evidence_sha
    assert s3_data == test_evidence_bytes
    print(f"Verified Evidence Accessibility: S3 artifact intact and bound to restored case.")

    # 7. Cleanup
    print("\n" + "-" * 70)
    print("STEP 7: Cleanup Test Artifacts")
    print("-" * 70)

    await case_manager.delete_case(original_case_id, delete_evidence_files=True)
    if backup_path.exists():
        backup_path.unlink()
    print("Cleaned up restored case and temporary local backup archive.")

    print("\n" + "=" * 80)
    print("BACKUP & DISASTER RECOVERY AUDIT PASSED 100%.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_backup_and_disaster_recovery_audit())
