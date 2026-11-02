import asyncio
import os
import sys
import time
import subprocess
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent
root_dir = backend_dir.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.storage.backup_system import backup_system, MAGIC_HEADER

async def test_backup_security_suite():
    print("=" * 80)
    print("PRAVISION PHASE 2.4 — BACKUP ENCRYPTION & SECURITY AUDIT")
    print("=" * 80)
    start_time = time.time()

    # 1. Key Isolation Check in Git
    print("\n" + "-" * 70)
    print("CHECK 1: Git Ignore Verification for Backup Artifacts & Keys")
    print("-" * 70)
    res_key = subprocess.run(["git", "check-ignore", "backend/.backup_key"], cwd=str(root_dir), capture_output=True, text=True)
    res_bkp = subprocess.run(["git", "check-ignore", "backend/backups/test.pravision_bkp"], cwd=str(root_dir), capture_output=True, text=True)
    assert ".backup_key" in res_key.stdout
    assert ".pravision_bkp" in res_bkp.stdout
    print("[PASS] Git strictly ignores .backup_key and .pravision_bkp files.")

    # 2. AES-256-GCM Indecipherability
    print("\n" + "-" * 70)
    print("CHECK 2: Ciphertext Indecipherability Test")
    print("-" * 70)
    secret_payload = b'{"case_title": "TOP SECRET CLASSIFIED INTELLIGENCE DOSSIER #9901"}'
    encrypted = backup_system.encrypt_payload(secret_payload)
    assert encrypted.startswith(MAGIC_HEADER)
    assert b"TOP SECRET" not in encrypted
    assert b"CLASSIFIED" not in encrypted
    print("[PASS] Ciphertext successfully hides all plaintext strings.")

    # 3. Decryption with Correct Key
    decrypted = backup_system.decrypt_payload(encrypted)
    assert decrypted == secret_payload
    print("[PASS] Decryption with authorized key succeeds and matches plaintext perfectly.")

    # 4. Rejection with Wrong Key
    print("\n" + "-" * 70)
    print("CHECK 3: Unauthorized Access / Wrong Key Rejection")
    print("-" * 70)
    wrong_key = AESGCM.generate_key(bit_length=256)
    rejected = False
    try:
        backup_system.decrypt_payload(encrypted, key=wrong_key)
    except Exception as e:
        rejected = True
        print(f"Correctly caught unauthorized key attempt: {e}")
    assert rejected is True
    print("[PASS] Unauthorized decryption key strictly rejected.")

    # 5. Tamper-Proof Integrity (Bit-Flipping Detection)
    print("\n" + "-" * 70)
    print("CHECK 4: Cryptographic Bit-Flip Tampering Detection")
    print("-" * 70)
    tampered_bytes = bytearray(encrypted)
    # Flip a bit in the ciphertext / tag region
    tampered_bytes[-5] ^= 0x01
    tamper_caught = False
    try:
        backup_system.decrypt_payload(bytes(tampered_bytes))
    except Exception as e:
        tamper_caught = True
        print(f"Correctly detected cryptographic tampering: {e}")
    assert tamper_caught is True
    print("[PASS] Any bit alteration immediately fails GCM tag authentication.")

    duration = time.time() - start_time
    print(f"\nExecution Duration: {duration:.2f}s")
    print("=" * 80)
    print("ALL BACKUP SECURITY AUDIT CHECKS PASSED 100%.")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_backup_security_suite())

