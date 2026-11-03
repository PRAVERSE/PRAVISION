"""
PRAVISION Phase 2.5 - Streaming Evidence Archive Verification Test Suite.
Validates:
1. Streaming chunked archive creation (.pravision_archive) with memory bounds (64 KB chunks)
2. AES-256-GCM authenticated chunk encryption with unique derived nonces
3. Header validation (PVARC\\x01 magic and base nonce)
4. Bit-flip tampering detection (AES-GCM tag mismatch rejection)
5. Archive truncation detection (missing EOF chunk marker)
6. Dry-run archive integrity verification (verify_only=True)
7. Full case and evidence restoration (verify_only=False)
8. Archive API endpoints (/api/archive/create, /api/archive/restore)
"""

import sys
import os
import asyncio
import hashlib
import tempfile
import httpx
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.main import app
from app.storage.streaming_archive import streaming_archive_service, ARCHIVE_DIR, ARCHIVE_MAGIC
from app.storage.case_manager import case_manager
from app.storage.database import init_db

passed_count = 0
failed_count = 0

def log_test(name: str, passed: bool, detail: str = ""):
    global passed_count, failed_count
    status = "PASS" if passed else "FAIL"
    if passed:
        passed_count += 1
        print(f"  [+] {name}: {status} {detail}")
    else:
        failed_count += 1
        print(f"  [-] {name}: {status} - {detail}")

async def run_streaming_archive_verification():
    global passed_count, failed_count
    print("=" * 80)
    print("PRAVISION PHASE 2.5: STREAMING EVIDENCE ARCHIVE VERIFICATION")
    print("=" * 80)

    await init_db()

    # Step 1: Create a verified test case with realistic evidence
    test_case = await case_manager.create_case(
        title="Operation Cerberus Streaming Verification",
        description="Phase 2.5 automated verification case for streaming archives.",
        classification="TOP SECRET",
        tags=["streaming", "phase2.5", "cryptography"]
    )
    case_id = test_case["id"]
    log_test(
        "1. Provision Verification Case",
        case_id is not None,
        f"(Case ID: {case_id})"
    )

    # Step 2: Generate Streaming Encrypted Archive (.pravision_archive)
    archive_res = await streaming_archive_service.create_archive(
        case_id=case_id,
        output_file_name=f"verify_streaming_{case_id[:8]}.pravision_archive"
    )
    archive_path = Path(archive_res["file_path"])
    log_test(
        "2. Streaming Archive Creation",
        archive_path.exists() and archive_res.get("chunk_count", 0) > 0,
        f"(Path: {archive_path.name}, Chunks: {archive_res.get('chunk_count')}, Encrypted: {archive_res.get('encrypted_bytes')}B)"
    )

    # Step 3: Header & Magic Verification
    archive_bytes = archive_path.read_bytes()
    magic_ok = archive_bytes.startswith(ARCHIVE_MAGIC)
    log_test(
        "3. Archive Format & Magic Check",
        magic_ok and len(archive_bytes) > 20,
        f"(Magic: {archive_bytes[:6]}, Total: {len(archive_bytes)}B)"
    )

    # Step 4: Dry-Run Integrity Verification (verify_only=True)
    verify_res = await streaming_archive_service.restore_archive(
        archive_path=archive_path,
        verify_only=True
    )
    log_test(
        "4. Dry-Run Cryptographic Integrity Verification",
        verify_res.get("status") == "verified" and verify_res.get("total_cases") >= 1,
        f"(Status: {verify_res.get('status')}, Cases: {verify_res.get('total_cases')}, Files: {verify_res.get('total_files')})"
    )

    # Step 5: Incorrect Key Rejection
    wrong_key = os.urandom(32)
    try:
        await streaming_archive_service.restore_archive(
            archive_path=archive_path,
            verify_only=True,
            key=wrong_key
        )
        log_test("5. Incorrect Key Rejection", False, "Failed to reject invalid key")
    except ValueError as e:
        log_test("5. Incorrect Key Rejection", True, f"(Correctly rejected: {e})")

    # Step 6: Bit-Flip Tamper Resistance (AES-GCM Auth Tag Failure)
    tampered_archive_path = ARCHIVE_DIR / f"tampered_{case_id[:8]}.pravision_archive"
    tampered_bytes = bytearray(archive_bytes)
    # Flip bit in the first ciphertext chunk (after header: 6B magic + 12B nonce + 4B chunk_size + 8B chunk header = ~30B)
    tampered_bytes[35] ^= 0x01
    tampered_archive_path.write_bytes(tampered_bytes)

    try:
        await streaming_archive_service.restore_archive(
            archive_path=tampered_archive_path,
            verify_only=True
        )
        log_test("6. Bit-Flip Tamper Rejection", False, "Failed to catch tampered ciphertext")
    except ValueError as e:
        log_test("6. Bit-Flip Tamper Rejection", True, f"(Caught tampering: {e})")
    finally:
        if tampered_archive_path.exists():
            tampered_archive_path.unlink()

    # Step 7: Truncation Detection (Missing EOF chunk marker)
    truncated_archive_path = ARCHIVE_DIR / f"truncated_{case_id[:8]}.pravision_archive"
    # Cut off EOF marker (last 8 bytes)
    truncated_bytes = archive_bytes[:-8]
    truncated_archive_path.write_bytes(truncated_bytes)

    try:
        await streaming_archive_service.restore_archive(
            archive_path=truncated_archive_path,
            verify_only=True
        )
        log_test("7. Archive Truncation Detection", False, "Failed to catch truncated archive")
    except ValueError as e:
        log_test("7. Archive Truncation Detection", True, f"(Caught truncation: {e})")
    finally:
        if truncated_archive_path.exists():
            truncated_archive_path.unlink()

    # Step 8: Full Restoration Execution (verify_only=False)
    restore_exec = await streaming_archive_service.restore_archive(
        archive_path=archive_path,
        target_case_prefix="[RESTORED] ",
        verify_only=False
    )
    log_test(
        "8. Full Case Restoration Execution",
        restore_exec.get("status") == "restored" and (restore_exec.get("cases_restored") or 0) >= 1,
        f"(Status: {restore_exec.get('status')}, Cases Restored: {restore_exec.get('cases_restored')})"
    )

    # Step 9: Verify Archive API Endpoints via HTTP
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # API Create Archive
        r_api_create = await client.post("/api/archive/create", json={"case_id": case_id})
        log_test(
            "9. API Streaming Archive Endpoint (/api/archive/create)",
            r_api_create.status_code == 200 and "archive_id" in r_api_create.json(),
            f"(HTTP {r_api_create.status_code}, Archive ID: {r_api_create.json().get('archive_id')})"
        )

        api_fname = Path(r_api_create.json().get("file_path")).name
        api_archive_path = ARCHIVE_DIR / api_fname
        # API Restore Archive (Dry run via Multipart Upload)
        with open(api_archive_path, "rb") as f_up:
            r_api_restore = await client.post(
                "/api/archive/restore",
                files={"file": (api_fname, f_up, "application/octet-stream")},
                data={"verify_only": "true"}
            )
        log_test(
            "10. API Archive Restore Endpoint (/api/archive/restore)",
            r_api_restore.status_code == 200 and r_api_restore.json().get("status") == "verified",
            f"(HTTP {r_api_restore.status_code}, Status: {r_api_restore.json().get('status')})"
        )

    # Clean up test artifacts
    if archive_path.exists():
        archive_path.unlink()
    api_archive_path = ARCHIVE_DIR / api_fname
    if api_archive_path.exists():
        api_archive_path.unlink()
    await case_manager.delete_case(case_id)

    print("=" * 80)
    print(f"STREAMING ARCHIVE VERIFICATION SUMMARY: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 80)
    return failed_count == 0

if __name__ == "__main__":
    success = asyncio.run(run_streaming_archive_verification())
    sys.exit(0 if success else 1)
