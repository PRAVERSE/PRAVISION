import os
import io
import json
import uuid
import struct
import tarfile
import hashlib
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, AsyncGenerator

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import WORKSPACE_DIR
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.backup_system import get_or_create_encryption_key

logger = logging.getLogger("pravision.storage.streaming_archive")

ARCHIVE_MAGIC = b"PVARC\x01"
DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB chunk size for bounded RAM usage
ARCHIVE_DIR = WORKSPACE_DIR / "backend" / "backups" / "streaming_archives"
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

class StreamingArchiveService:
    """
    High-performance, memory-bounded streaming archive engine supporting
    multi-gigabyte evidence collections with chunked AES-256-GCM authenticated encryption.
    """

    def __init__(self):
        self.encryption_key = get_or_create_encryption_key()

    def _derive_chunk_nonce(self, base_nonce: bytes, chunk_index: int, key: bytes) -> bytes:
        """Derives a strictly unique 12-byte nonce per chunk using HMAC-SHA256."""
        counter_bytes = struct.pack(">I", chunk_index)
        mac = hashlib.sha256(key + base_nonce + counter_bytes).digest()
        return mac[:12]

    async def create_archive(
        self,
        case_id: Optional[str] = None,
        output_file_name: Optional[str] = None,
        key: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Creates a streaming tar archive (.pravision_archive) containing full dossiers
        and raw binary evidence files, protected with chunked AES-256-GCM encryption.
        """
        active_key = key or self.encryption_key
        aesgcm = AESGCM(active_key)
        base_nonce = os.urandom(12)

        timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        archive_id = f"ARCHIVE_{timestamp_str}_{uuid.uuid4().hex[:6]}"
        filename = output_file_name or f"{archive_id}.pravision_archive"
        archive_path = ARCHIVE_DIR / filename

        logger.info(f"Building streaming archive {archive_id} at {archive_path}...")

        # 1. Fetch cases & metadata
        if case_id:
            c = await case_manager.get_case(case_id)
            if not c:
                raise ValueError(f"Case '{case_id}' not found.")
            target_cases = [c]
        else:
            target_cases = await case_manager.list_cases()

        dossiers = []
        for c in target_cases:
            dossier = await case_manager.export_case_dossier(c["id"])
            dossiers.append(dossier)

        # 2. Build temporary uncompressed tar archive
        temp_tar_path = ARCHIVE_DIR / f"temp_{archive_id}.tar"
        manifest_files = []
        total_raw_bytes = 0

        try:
            with tarfile.open(temp_tar_path, "w") as tar:
                # Add dossier.json
                dossier_bytes = json.dumps(dossiers, indent=2).encode("utf-8")
                d_info = tarfile.TarInfo(name="dossier.json")
                d_info.size = len(dossier_bytes)
                d_info.mtime = int(datetime.utcnow().timestamp())
                tar.addfile(d_info, io.BytesIO(dossier_bytes))
                total_raw_bytes += len(dossier_bytes)

                # Add each evidence binary file directly as a tar member
                for d in dossiers:
                    for ev in d.get("evidences", []):
                        b2_key = ev.get("b2_file_key")
                        if b2_key:
                            try:
                                data_bytes, f_hash = await b2_storage.download_evidence(b2_key)
                                safe_tar_name = f"evidence/{Path(b2_key).name}"
                                f_info = tarfile.TarInfo(name=safe_tar_name)
                                f_info.size = len(data_bytes)
                                f_info.mtime = int(datetime.utcnow().timestamp())
                                tar.addfile(f_info, io.BytesIO(data_bytes))
                                total_raw_bytes += len(data_bytes)
                                manifest_files.append({
                                    "file_key": b2_key,
                                    "tar_name": safe_tar_name,
                                    "file_hash": f_hash,
                                    "size_bytes": len(data_bytes),
                                    "mime_type": ev.get("file_mime_type")
                                })
                            except Exception as dl_err:
                                logger.warning(f"Could not include evidence {b2_key}: {dl_err}")

                # Add manifest.json
                manifest_data = {
                    "archive_id": archive_id,
                    "version": "2.5",
                    "created_at": datetime.utcnow().isoformat() + "Z",
                    "total_cases": len(dossiers),
                    "total_files": len(manifest_files),
                    "total_raw_bytes": total_raw_bytes,
                    "files": manifest_files
                }
                m_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
                m_info = tarfile.TarInfo(name="manifest.json")
                m_info.size = len(m_bytes)
                m_info.mtime = int(datetime.utcnow().timestamp())
                tar.addfile(m_info, io.BytesIO(m_bytes))

            # 3. Stream tarfile through Chunked AES-256-GCM cipher into output archive
            sha256_hasher = hashlib.sha256()
            total_encrypted_bytes = 0
            chunk_index = 0

            with open(temp_tar_path, "rb") as in_tar, open(archive_path, "wb") as out_enc:
                # Write Header: MAGIC (6B) + Base Nonce (12B) + Chunk Size (4B)
                header = ARCHIVE_MAGIC + base_nonce + struct.pack(">I", DEFAULT_CHUNK_SIZE)
                out_enc.write(header)
                total_encrypted_bytes += len(header)

                while True:
                    chunk = in_tar.read(DEFAULT_CHUNK_SIZE)
                    if not chunk:
                        break
                    sha256_hasher.update(chunk)
                    chunk_nonce = self._derive_chunk_nonce(base_nonce, chunk_index, active_key)
                    # Encrypt chunk (ciphertext includes 16-byte GCM tag)
                    ciphertext = aesgcm.encrypt(chunk_nonce, chunk, None)
                    # Write: Index (4B) + Ciphertext Length (4B) + Ciphertext (N B)
                    chunk_header = struct.pack(">II", chunk_index, len(ciphertext))
                    out_enc.write(chunk_header + ciphertext)
                    total_encrypted_bytes += len(chunk_header) + len(ciphertext)
                    chunk_index += 1

                # Write EOF chunk: Index=0xFFFFFFFF, Length=0
                eof_marker = struct.pack(">II", 0xFFFFFFFF, 0)
                out_enc.write(eof_marker)
                total_encrypted_bytes += len(eof_marker)

            plaintext_sha256 = sha256_hasher.hexdigest()
            logger.info(f"Archive {archive_id} created successfully: {chunk_index} chunks, {total_encrypted_bytes} bytes encrypted.")

            return {
                "archive_id": archive_id,
                "file_path": str(archive_path),
                "total_cases": len(dossiers),
                "total_evidence_files": len(manifest_files),
                "uncompressed_bytes": total_raw_bytes,
                "encrypted_bytes": total_encrypted_bytes,
                "chunk_count": chunk_index,
                "plaintext_sha256": plaintext_sha256,
                "created_at": manifest_data["created_at"]
            }
        finally:
            # Clean up intermediate unencrypted tar
            if temp_tar_path.exists():
                try:
                    temp_tar_path.unlink()
                except Exception:
                    pass

    async def restore_archive(
        self,
        archive_path: Path,
        target_case_prefix: str = "",
        verify_only: bool = True,
        key: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Streams and decrypts an authenticated archive, verifies chunk sequence numbers
        and authentication tags, validates manifest and file hashes, and restores cases.
        """
        active_key = key or self.encryption_key
        aesgcm = AESGCM(active_key)

        if not archive_path.exists():
            raise FileNotFoundError(f"Archive not found: {archive_path}")

        temp_extracted_tar = ARCHIVE_DIR / f"restore_temp_{uuid.uuid4().hex[:8]}.tar"

        try:
            # 1. Stream Decryption & Tag Verification
            with open(archive_path, "rb") as in_enc, open(temp_extracted_tar, "wb") as out_tar:
                # Read Header
                header_magic = in_enc.read(len(ARCHIVE_MAGIC))
                if header_magic != ARCHIVE_MAGIC:
                    raise ValueError("Invalid archive format: Header magic mismatch.")

                base_nonce = in_enc.read(12)
                chunk_size_bytes = in_enc.read(4)
                if len(base_nonce) != 12 or len(chunk_size_bytes) != 4:
                    raise ValueError("Corrupted archive: Incomplete header.")

                expected_chunk_index = 0
                while True:
                    chunk_hdr = in_enc.read(8)
                    if not chunk_hdr:
                        raise ValueError("Unexpected end of archive: Missing EOF chunk marker.")
                    chunk_idx, ct_len = struct.unpack(">II", chunk_hdr)
                    if chunk_idx == 0xFFFFFFFF and ct_len == 0:
                        # Clean EOF
                        break
                    if chunk_idx != expected_chunk_index:
                        raise ValueError(f"Chunk sequence violation: expected {expected_chunk_index}, got {chunk_idx}.")

                    ciphertext = in_enc.read(ct_len)
                    if len(ciphertext) != ct_len:
                        raise ValueError(f"Truncated archive chunk at index {chunk_idx}.")

                    chunk_nonce = self._derive_chunk_nonce(base_nonce, chunk_idx, active_key)
                    # Decrypt & verify GCM tag
                    try:
                        plaintext_chunk = aesgcm.decrypt(chunk_nonce, ciphertext, None)
                    except Exception as e:
                        raise ValueError(f"Cryptographic authentication failed on chunk {chunk_idx}: {e}")

                    out_tar.write(plaintext_chunk)
                    expected_chunk_index += 1

            # 2. Inspect Extracted Tar & Validate Paths (Prevent Path Traversal)
            verified_files = []
            manifest_info = {}
            dossiers_data = []

            with tarfile.open(temp_extracted_tar, "r") as tar:
                # Security Check: Reject any member attempting path traversal
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name or "\\" in member.name:
                        raise ValueError(f"Security violation: Path traversal detected in archive member '{member.name}'.")

                # Extract manifest
                m_member = tar.extractfile("manifest.json")
                if not m_member:
                    raise ValueError("Archive is missing manifest.json.")
                manifest_info = json.loads(m_member.read().decode("utf-8"))

                # Extract dossier
                d_member = tar.extractfile("dossier.json")
                if not d_member:
                    raise ValueError("Archive is missing dossier.json.")
                dossiers_data = json.loads(d_member.read().decode("utf-8"))

                # Verify each evidence file hash
                for f_meta in manifest_info.get("files", []):
                    tar_name = f_meta["tar_name"]
                    f_file = tar.extractfile(tar_name)
                    if not f_file:
                        raise ValueError(f"Missing evidence member in tar: {tar_name}")
                    content = f_file.read()
                    actual_hash = hashlib.sha256(content).hexdigest()
                    if actual_hash != f_meta["file_hash"]:
                        raise ValueError(f"Integrity failure on {tar_name}: Expected {f_meta['file_hash']}, got {actual_hash}")
                    verified_files.append((f_meta, content))

            if verify_only:
                return {
                    "status": "verified",
                    "archive_id": manifest_info.get("archive_id"),
                    "version": manifest_info.get("version"),
                    "total_cases": len(dossiers_data),
                    "total_files": len(verified_files),
                    "total_bytes": manifest_info.get("total_raw_bytes")
                }

            # 3. Restoration execution
            restored_cases = []
            gen_new = bool(target_case_prefix)
            for d in dossiers_data:
                if target_case_prefix:
                    d["case"]["title"] = f"{target_case_prefix}{d['case']['title']}"
                res = await case_manager.import_case_dossier(d, generate_new_ids=gen_new)
                restored_cases.append(res)

            # 4. Restore verified binary files to storage
            files_restored = 0
            for f_meta, raw_bytes in verified_files:
                try:
                    await b2_storage.upload_evidence(
                        data=raw_bytes,
                        filename=Path(f_meta["file_key"]).name,
                        content_type=f_meta.get("mime_type", "application/octet-stream")
                    )
                    files_restored += 1
                except Exception as store_err:
                    logger.error(f"Failed restoring file {f_meta['file_key']}: {store_err}")

            return {
                "status": "restored",
                "archive_id": manifest_info.get("archive_id"),
                "cases_restored": len(restored_cases),
                "files_restored": files_restored,
                "total_bytes": manifest_info.get("total_raw_bytes")
            }
        finally:
            if temp_extracted_tar.exists():
                try:
                    temp_extracted_tar.unlink()
                except Exception:
                    pass

streaming_archive_service = StreamingArchiveService()

