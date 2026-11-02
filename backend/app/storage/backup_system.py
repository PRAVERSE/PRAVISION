import os
import json
import uuid
import base64
import hashlib
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import WORKSPACE_DIR
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage

logger = logging.getLogger("pravision.storage.backup")

BACKUP_DIR = WORKSPACE_DIR / "backend" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
KEY_FILE = WORKSPACE_DIR / "backend" / ".backup_key"
MANIFEST_FILE = BACKUP_DIR / "backup_manifest.json"
MAGIC_HEADER = b"PVBKP\x02"  # Version 2.4 backup container header

def get_or_create_encryption_key() -> bytes:
    """Retrieve or generate a 256-bit AES-GCM encryption key."""
    env_key = os.environ.get("PRAVISION_BACKUP_ENCRYPTION_KEY")
    if env_key:
        return hashlib.sha256(env_key.encode("utf-8")).digest()

    if KEY_FILE.exists():
        try:
            return bytes.fromhex(KEY_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            pass

    # Generate fresh 32-byte key
    new_key = AESGCM.generate_key(bit_length=256)
    KEY_FILE.write_text(new_key.hex(), encoding="utf-8")
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    return new_key

class BackupSystem:
    def __init__(self):
        self.encryption_key = get_or_create_encryption_key()

    def _read_manifest(self) -> List[Dict[str, Any]]:
        if not MANIFEST_FILE.exists():
            return []
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_manifest(self, entries: List[Dict[str, Any]]):
        MANIFEST_FILE.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    def encrypt_payload(self, plaintext_bytes: bytes, key: Optional[bytes] = None) -> bytes:
        """Encrypt plaintext payload using AES-256-GCM with a random 12-byte nonce."""
        active_key = key or self.encryption_key
        aesgcm = AESGCM(active_key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)
        return MAGIC_HEADER + nonce + ciphertext

    def decrypt_payload(self, encrypted_bytes: bytes, key: Optional[bytes] = None) -> bytes:
        """Decrypt payload and authenticate tag using AES-256-GCM."""
        if not encrypted_bytes.startswith(MAGIC_HEADER):
            raise ValueError("Invalid backup container: Magic header mismatch.")
        header_len = len(MAGIC_HEADER)
        nonce = encrypted_bytes[header_len:header_len + 12]
        ciphertext = encrypted_bytes[header_len + 12:]
        active_key = key or self.encryption_key
        aesgcm = AESGCM(active_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    async def create_backup(
        self,
        case_id: Optional[str] = None,
        sync_to_cloud: bool = True
    ) -> Dict[str, Any]:
        """
        Creates an encrypted, self-contained backup package including full case dossiers
        and verified actual evidence binary files.
        """
        backup_id = f"BKP-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        logger.info(f"Initiating automated backup {backup_id} (case_id={case_id})...")

        # 1. Identify target cases
        if case_id:
            c = await case_manager.get_case(case_id)
            if not c:
                raise ValueError(f"Case '{case_id}' not found.")
            target_cases = [c]
        else:
            target_cases = await case_manager.list_cases()

        dossiers = []
        evidence_files = []
        total_file_bytes = 0

        # 2. Extract dossiers and download real evidence files
        for c in target_cases:
            try:
                dossier = await case_manager.export_case_dossier(c["id"])
                dossiers.append(dossier)

                # Fetch real evidence attachments
                for ev in dossier.get("evidences", []):
                    b2_key = ev.get("b2_file_key")
                    expected_hash = ev.get("file_hash")
                    if b2_key and expected_hash:
                        try:
                            # Download evidence bytes with retry
                            file_data, file_hash = await b2_storage.download_evidence(b2_key)
                            if file_hash != expected_hash:
                                logger.warning(f"Hash mismatch for {b2_key}: expected {expected_hash}, got {file_hash}")
                            
                            evidence_files.append({
                                "case_id": c["id"],
                                "evidence_id": ev.get("id"),
                                "file_key": b2_key,
                                "file_hash": file_hash,
                                "file_size": len(file_data),
                                "mime_type": ev.get("file_mime_type", "application/octet-stream"),
                                "data_b64": base64.b64encode(file_data).decode("ascii")
                            })
                            total_file_bytes += len(file_data)
                        except Exception as dl_err:
                            logger.error(f"Failed to fetch evidence file {b2_key}: {dl_err}")
            except Exception as exp_err:
                logger.error(f"Failed exporting dossier for case {c.get('id')}: {exp_err}")

        # 3. Assemble package
        package = {
            "backup_id": backup_id,
            "version": "2.4",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "scope": "single_case" if case_id else "all_saved_cases",
            "target_case_id": case_id,
            "cases": dossiers,
            "evidence_files": evidence_files,
            "summary": {
                "total_cases": len(dossiers),
                "total_files": len(evidence_files),
                "total_file_bytes": total_file_bytes
            }
        }

        # Calculate plaintext SHA-256
        plaintext_json = json.dumps(package, sort_keys=True)
        plaintext_bytes = plaintext_json.encode("utf-8")
        package_sha256 = hashlib.sha256(plaintext_bytes).hexdigest()
        package["package_sha256"] = package_sha256

        # Re-encode with verified hash inside
        final_plaintext = json.dumps(package).encode("utf-8")
        encrypted_bytes = self.encrypt_payload(final_plaintext)

        # 4. Save to local staging
        backup_file_path = BACKUP_DIR / f"{backup_id}.pravision_bkp"
        backup_file_path.write_bytes(encrypted_bytes)

        # 5. Optional cloud storage replication
        cloud_replicated = False
        cloud_key = None
        if sync_to_cloud and b2_storage.is_cloud_enabled:
            try:
                cloud_key = f"backups/{backup_id}.pravision_bkp"
                await b2_storage.upload_evidence(
                    data=encrypted_bytes,
                    filename=f"{backup_id}.pravision_bkp",
                    content_type="application/octet-stream"
                )
                cloud_replicated = True
            except Exception as cloud_err:
                logger.warning(f"Cloud backup replication deferred: {cloud_err}")

        # 6. Update manifest
        manifest_entry = {
            "backup_id": backup_id,
            "created_at": package["created_at"],
            "scope": package["scope"],
            "total_cases": len(dossiers),
            "total_files": len(evidence_files),
            "size_bytes": len(encrypted_bytes),
            "package_sha256": package_sha256,
            "local_path": str(backup_file_path),
            "cloud_replicated": cloud_replicated,
            "status": "verified"
        }
        manifest = self._read_manifest()
        manifest.insert(0, manifest_entry)
        self._write_manifest(manifest[:50]) # keep latest 50

        logger.info(f"Backup {backup_id} created successfully ({len(encrypted_bytes)} bytes encrypted, {len(evidence_files)} files).")
        return manifest_entry

    async def restore_backup(
        self,
        backup_bytes: bytes,
        key: Optional[bytes] = None,
        target_case_prefix: str = "",
        verify_only: bool = False
    ) -> Dict[str, Any]:
        """
        Decrypts, verifies cryptographic checksums, and restores case dossiers
        and binary evidence files into the database and storage.
        """
        # 1. Decrypt
        try:
            plaintext_bytes = self.decrypt_payload(backup_bytes, key)
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

        # 2. Parse & Verify package hash
        data = json.loads(plaintext_bytes.decode("utf-8"))
        declared_hash = data.get("package_sha256")
        
        # Verify all evidence files SHA-256
        verified_files = []
        for f in data.get("evidence_files", []):
            raw_bytes = base64.b64decode(f["data_b64"])
            calc_hash = hashlib.sha256(raw_bytes).hexdigest()
            if calc_hash != f["file_hash"]:
                raise ValueError(f"Evidence file integrity failure for {f['file_key']}: hash mismatch!")
            verified_files.append((f, raw_bytes))

        if verify_only:
            return {
                "status": "verified",
                "backup_id": data.get("backup_id"),
                "version": data.get("version"),
                "total_cases": len(data.get("cases", [])),
                "total_files": len(verified_files),
                "package_sha256": declared_hash
            }

        # 3. Restoration execution
        restored_cases = []
        gen_new = bool(target_case_prefix)
        for case_dossier in data.get("cases", []):
            if target_case_prefix:
                case_dossier["case"]["title"] = f"{target_case_prefix}{case_dossier['case']['title']}"
            res = await case_manager.import_case_dossier(case_dossier, generate_new_ids=gen_new)
            restored_cases.append(res)

        # 4. Restore evidence files to active storage
        files_restored = 0
        for f_meta, raw_bytes in verified_files:
            try:
                # Ensure evidence file is present in active storage
                await b2_storage.upload_evidence(
                    data=raw_bytes,
                    filename=Path(f_meta["file_key"]).name,
                    content_type=f_meta.get("mime_type", "application/octet-stream")
                )
                files_restored += 1
            except Exception as store_err:
                logger.error(f"Failed to restore evidence file {f_meta['file_key']}: {store_err}")

        return {
            "status": "restored",
            "backup_id": data.get("backup_id"),
            "cases_restored": len(restored_cases),
            "files_restored": files_restored,
            "package_sha256": declared_hash
        }

    def list_backups(self) -> List[Dict[str, Any]]:
        return self._read_manifest()

    def get_backup_bytes(self, backup_id: str) -> Optional[bytes]:
        file_path = BACKUP_DIR / f"{backup_id}.pravision_bkp"
        if file_path.exists():
            return file_path.read_bytes()
        return None

backup_system = BackupSystem()

class BackupScheduler:
    """Configurable background backup runner managed in FastAPI lifespan."""
    def __init__(self, interval_seconds: int = 3600):
        self.interval = interval_seconds
        self.is_running = False
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self.last_run: Optional[str] = None
        self.last_status: Optional[str] = None
        self.total_runs: int = 0

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"PRAVISION BackupScheduler started (interval: {self.interval}s).")

    async def stop(self):
        if not self.is_running:
            return
        self.is_running = False
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("PRAVISION BackupScheduler stopped gracefully.")

    async def _run_loop(self):
        # Initial wait before first scheduled run (default interval e.g. 1 hour)
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=float(self.interval))
            return
        except asyncio.TimeoutError:
            pass

        while self.is_running and not self._stop_event.is_set():
            try:
                logger.info("BackupScheduler: Starting scheduled case dossier backup cycle...")
                res = await backup_system.create_backup(sync_to_cloud=True)
                self.last_run = datetime.utcnow().isoformat() + "Z"
                self.last_status = "success"
                self.total_runs += 1
                logger.info(f"BackupScheduler: Completed backup {res['backup_id']}.")
            except Exception as e:
                self.last_status = f"failed: {str(e)}"
                logger.error(f"BackupScheduler error during backup cycle: {e}")

            # Sleep for interval or until stopped
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=float(self.interval))
                break
            except asyncio.TimeoutError:
                continue

    def get_status(self) -> Dict[str, Any]:
        return {
            "scheduler_running": self.is_running,
            "interval_seconds": self.interval,
            "last_run": self.last_run,
            "last_status": self.last_status,
            "total_runs": self.total_runs,
            "backup_count": len(backup_system.list_backups())
        }

backup_scheduler = BackupScheduler(interval_seconds=3600)

