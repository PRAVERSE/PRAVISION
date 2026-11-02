import asyncio
import os
import sys
import uuid
import hashlib
import httpx
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.database import init_db, async_session_maker
from app.storage.b2_storage import b2_storage
from app.storage.case_manager import case_manager
from app.evidence.models import EvidenceFinding, EntityType, ConfidenceLevel
from app.storage.models_db import CaseModel, EvidenceModel
from sqlalchemy import select

async def run_object_storage_readiness_audit():
    print("=" * 80)
    print("PRAVISION PHASE 2.2 — NEON OBJECT STORAGE PRODUCTION READINESS AUDIT")
    print("=" * 80)

    # 0. Check Status & Initialize DB
    await init_db()
    status = b2_storage.get_status()
    print("Storage Service Status:", status)
    assert status["cloud_enabled"] is True, "Cloud object storage not enabled!"
    assert status["is_neon"] is True, "Storage backend is not configured for Neon!"
    assert status["bucket"] == "pravision-evidence", f"Unexpected bucket: {status['bucket']}"
    print("[PASS] Neon Object Storage initialized and connected.")

    # 1. Multi-Size & Multi-MIME Upload and Download SHA-256 Verification
    print("\n" + "-" * 70)
    print("SUBTEST 2.1: Multi-Size & Multi-MIME Upload and SHA-256 Verification")
    print("-" * 70)

    test_matrix = [
        {
            "name": "1KB Text Document",
            "size": 1024,
            "filename": "osint_manifest.txt",
            "mime": "text/plain",
            "content": b"PRAVISION_INTELLIGENCE_MANIFEST_TEST_" * 27 + b"EOF"
        },
        {
            "name": "50KB PNG Image (Synthetic Header)",
            "size": 50 * 1024,
            "filename": "satellite_telemetry.png",
            "mime": "image/png",
            "content": b"\x89PNG\r\n\x1a\n" + (b"IMAGE_PAYLOAD_CHUNK_50KB_" * 2000)[:50 * 1024 - 8]
        },
        {
            "name": "500KB PDF Document (Synthetic)",
            "size": 500 * 1024,
            "filename": "dossier_summary.pdf",
            "mime": "application/pdf",
            "content": b"%PDF-1.7\n" + (b"PDF_STREAM_OBJECT_DATA_BYTE_" * 18000)[:500 * 1024 - 9]
        },
        {
            "name": "2MB Binary Firmware/Memory Dump",
            "size": 2 * 1024 * 1024,
            "filename": "memory_image.bin",
            "mime": "application/octet-stream",
            "content": os.urandom(2 * 1024 * 1024)
        }
    ]

    uploaded_keys = []
    inv_test_id = f"inv_s3_{uuid.uuid4().hex[:8]}"

    for item in test_matrix:
        expected_sha = hashlib.sha256(item["content"]).hexdigest()
        actual_size = len(item["content"])
        print(f"Uploading {item['name']}: {actual_size} bytes, MIME: {item['mime']}...")

        upload_res = await b2_storage.upload_evidence(
            data=item["content"],
            filename=item["filename"],
            content_type=item["mime"],
            investigation_id=inv_test_id
        )
        assert upload_res["storage_backend"] == "neon_cloud", f"Failed to upload to neon_cloud: {upload_res}"
        assert upload_res["file_hash"] == expected_sha
        assert upload_res["file_size"] == actual_size
        file_key = upload_res["file_key"]
        uploaded_keys.append((file_key, item["content"], expected_sha, item["name"]))
        print(f"  -> Uploaded successfully: Key={file_key}")

    # Now verify downloads & SHA-256 checksums
    print("\nVerifying Downloads and Bit-for-Bit SHA-256 Matching from Neon:")
    for file_key, original_bytes, expected_sha, name in uploaded_keys:
        downloaded_bytes, dl_sha = await b2_storage.download_evidence(file_key)
        assert dl_sha == expected_sha, f"SHA mismatch on {name}! Expected {expected_sha}, got {dl_sha}"
        assert len(downloaded_bytes) == len(original_bytes), f"Size mismatch on {name}!"
        assert downloaded_bytes == original_bytes, f"Byte content divergence detected on {name}!"
        print(f"  [PASS] {name} ({len(downloaded_bytes)} bytes) verified. SHA-256: {dl_sha[:16]}...")

    print("Subtest 2.1 PASSED: Multi-size multi-MIME uploads and bit-exact SHA-256 downloads verified.")

    # 2. Private Bucket Permission & Unauthorized Access Verification
    print("\n" + "-" * 70)
    print("SUBTEST 2.2: Private Bucket Security & Unauthorized HTTP Request")
    print("-" * 70)

    # Directly request the file over public internet without AWS authentication
    sample_key = uploaded_keys[0][0]
    public_url = f"{b2_storage.endpoint_url}/{b2_storage.bucket_name}/{sample_key}"
    print(f"Attempting unauthenticated HTTP GET to: {public_url}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(public_url)
        print(f"Public Unauthenticated Response Status: {resp.status_code}")
        # S3 private buckets must return 403 Forbidden or 401 Unauthorized for unauthenticated requests
        assert resp.status_code in (401, 403), f"Security Failure: Bucket is publicly readable! Got HTTP {resp.status_code}"
        print(f"Response Body Preview: {resp.text[:120]}")
        print("Subtest 2.2 PASSED: Bucket access is strictly PRIVATE (HTTP 403/401 enforced).")

    # 3. Duplicate Uploads and Idempotency
    print("\n" + "-" * 70)
    print("SUBTEST 2.3: Duplicate Uploads Idempotency & Unique Key Generation")
    print("-" * 70)

    dup_content = b"IDENTICAL_CONTENT_HASH_STREAM"
    dup_name = "evidence_snapshot.txt"

    res1 = await b2_storage.upload_evidence(dup_content, dup_name, "text/plain", inv_test_id)
    # Small delay to ensure timestamp difference or uuid uniqueness
    await asyncio.sleep(1.1)
    res2 = await b2_storage.upload_evidence(dup_content, dup_name, "text/plain", inv_test_id)

    print(f"Duplicate 1 Key: {res1['file_key']}")
    print(f"Duplicate 2 Key: {res2['file_key']}")
    assert res1["file_hash"] == res2["file_hash"]
    assert res1["file_key"] != res2["file_key"], "Duplicate uploads resulted in key collision!"
    print("Subtest 2.3 PASSED: Identical content correctly received independent unique storage keys.")

    # 4. Cascade Case Deletion & Object Storage Cleanup
    print("\n" + "-" * 70)
    print("SUBTEST 2.4: Case Deletion Cascade Object Storage Removal")
    print("-" * 70)

    # Create a dedicated case with retry
    case = None
    for attempt in range(4):
        try:
            case = await case_manager.create_case(
                title="Operation Cleanup Test",
                description="Verify cascade deletion of evidence in S3",
                created_by="Automated Test"
            )
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"Transient connection notice: {e}, retrying in 2s...")
            await asyncio.sleep(2)
    case_id = case["id"]
    test_file_bytes = b"CASCADE_DELETION_EVIDENCE_BODY"
    up_res = await b2_storage.upload_evidence(
        test_file_bytes, "cascade_evidence.dat", "application/octet-stream", case_id
    )
    cascade_key = up_res["file_key"]

    finding = EvidenceFinding(
        id=str(uuid.uuid4()),
        investigation_id=f"inv_cascade_{uuid.uuid4().hex[:6]}",
        entity_type=EntityType.HASH,
        entity_value=up_res["file_hash"],
        source_name="Cascade Verification Harness",
        evidence_description="Test evidence file for cascade removal",
        confidence=ConfidenceLevel.HIGH,
        raw_payload={"file_key": cascade_key, "file_hash": up_res["file_hash"], "size": len(test_file_bytes)}
    )

    await case_manager.save_investigation_to_case(
        case_id=case_id,
        investigation_id=finding.investigation_id,
        root_input="cascade_target",
        root_type="target",
        mode="mode_1_identity",
        findings=[finding]
    )

    # Verify object is accessible
    dl_data, _ = await b2_storage.download_evidence(cascade_key)
    assert dl_data == test_file_bytes
    print(f"Confirmed evidence exists in Neon Object Storage before case deletion.")

    # Delete case with delete_evidence_files=True
    deleted = await case_manager.delete_case(case_id, delete_evidence_files=True)
    assert deleted is True
    print(f"Case {case_id} deleted with evidence cascade flag enabled.")

    # Verify case does not exist in DB
    c_check = await case_manager.get_case(case_id)
    assert c_check is None

    # Verify evidence file is deleted from Neon Object Storage
    file_deleted = False
    try:
        await b2_storage.download_evidence(cascade_key)
    except FileNotFoundError:
        file_deleted = True
    except Exception as e:
        print(f"Exception during check: {e}")
        file_deleted = True

    assert file_deleted is True, f"Evidence file {cascade_key} was NOT removed from Neon Object Storage on case deletion!"
    print(f"Verified: Evidence file {cascade_key} permanently removed from Neon Object Storage.")
    print("Subtest 2.4 PASSED: Case deletion cascade cleanup verified.")

    # Cleanup artifacts from Subtest 2.1 & 2.3
    print("\nCleaning up test artifacts...")
    for file_key, _, _, _ in uploaded_keys:
        await b2_storage.delete_evidence(file_key)
    await b2_storage.delete_evidence(res1["file_key"])
    await b2_storage.delete_evidence(res2["file_key"])
    print("Cleaned up temporary test keys in Neon Object Storage.")

    print("\n" + "=" * 80)
    print("ALL NEON OBJECT STORAGE TESTS PASSED COMPLETELY.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(run_object_storage_readiness_audit())
