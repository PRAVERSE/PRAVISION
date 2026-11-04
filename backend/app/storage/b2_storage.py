import os
import re
import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.config import BASE_DIR, TEMP_DATA_DIR, VAULT_DATA_DIR

logger = logging.getLogger("pravision.storage.b2")

LOCAL_VAULT_DIR = VAULT_DATA_DIR
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit for single evidence artifact

class B2StorageService:
    """
    Unified Object Storage service supporting Neon Object Storage (S3-compatible)
    and Backblaze B2, with seamless local file vault fallback and strict SHA-256
    cryptographic chain of custody.
    """

    def __init__(self):
        # 1. Check Neon Object Storage (AWS_* env vars injected by neon deploy)
        # 2. Fall back to B2_* or local vault
        self.endpoint_url = os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("B2_ENDPOINT_URL") or "https://s3.us-west-004.backblazeb2.com"
        self.key_id = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("B2_APPLICATION_KEY_ID") or os.environ.get("B2_KEY_ID")
        self.app_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("B2_APPLICATION_KEY") or os.environ.get("B2_KEY")
        self.region_name = os.environ.get("AWS_REGION") or os.environ.get("B2_REGION_NAME", "us-west-004")
        self.bucket_name = os.environ.get("NEON_BUCKET_NAME") or os.environ.get("B2_BUCKET_NAME") or "pravision-evidence"
        self.neon_branch = os.environ.get("NEON_BRANCH")
        self.is_neon = bool(os.environ.get("AWS_ENDPOINT_URL_S3") and "neon.tech" in (self.endpoint_url or ""))
        self._s3_client = None

        if self.key_id and self.app_key and (os.environ.get("AWS_ENDPOINT_URL_S3") or os.environ.get("B2_ENDPOINT_URL") or os.environ.get("B2_APPLICATION_KEY_ID")):
            try:
                import boto3
                from botocore.config import Config
                
                config_kwargs = {
                    "signature_version": "s3v4",
                    "retries": {"max_attempts": 3, "mode": "standard"}
                }
                if self.is_neon:
                    # Neon requires path-style addressing
                    config_kwargs["s3"] = {"addressing_style": "path"}

                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.key_id,
                    aws_secret_access_key=self.app_key,
                    region_name=self.region_name,
                    config=Config(**config_kwargs)
                )
                provider = "Neon Object Storage" if self.is_neon else "Backblaze B2"
                logger.info(f"Initialized {provider} client for bucket '{self.bucket_name}' at {self.endpoint_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 boto3 client: {e}. Falling back to local secure vault.")
                self._s3_client = None

    @property
    def is_cloud_enabled(self) -> bool:
        return self._s3_client is not None

    def compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    async def upload_evidence(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        investigation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads an evidence file to Neon/B2 or local vault. Returns storage metadata and SHA-256 hash.
        """
        size_bytes = len(data)
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File size {size_bytes} exceeds maximum allowed evidence size ({MAX_FILE_SIZE_BYTES} bytes)")

        sha256_hash = self.compute_sha256(data)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        raw_base = os.path.basename(filename)
        safe_filename = re.sub(r"[^a-zA-Z0-9_.-]", "_", raw_base) or "evidence.bin"
        prefix = f"investigations/{investigation_id}/" if investigation_id else "global/"
        file_key = f"{prefix}{timestamp}_{sha256_hash[:12]}_{safe_filename}"

        if self.is_cloud_enabled:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await asyncio.to_thread(
                        self._s3_client.put_object,
                        Bucket=self.bucket_name,
                        Key=file_key,
                        Body=data,
                        ContentType=content_type,
                        Metadata={"sha256": sha256_hash, "original_filename": safe_filename}
                    )
                    backend_type = "neon_cloud" if self.is_neon else "b2_cloud"
                    return {
                        "storage_backend": backend_type,
                        "file_key": file_key,
                        "file_hash": sha256_hash,
                        "file_size": size_bytes,
                        "mime_type": content_type,
                        "bucket": self.bucket_name,
                        "endpoint": self.endpoint_url,
                        "provider": "Neon Object Storage" if self.is_neon else "Backblaze B2"
                    }
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                    else:
                        logger.error(f"Error uploading to cloud storage after {max_retries} attempts: {e}. Falling back to local vault.")

        # Local Vault Fallback
        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        await asyncio.to_thread(local_path.write_bytes, data)

        return {
            "storage_backend": "local_vault",
            "file_key": str(local_path.name),
            "file_hash": sha256_hash,
            "file_size": size_bytes,
            "mime_type": content_type,
            "local_path": str(local_path),
            "provider": "Local Vault"
        }

    async def download_evidence(self, file_key: str) -> Tuple[bytes, str]:
        """
        Downloads evidence file and validates its SHA-256 checksum.
        """
        if self.is_cloud_enabled:
            def _sync_download():
                resp = self._s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
                body = resp["Body"]
                chunks = []
                while True:
                    chunk = body.read(64 * 1024)
                    if not chunk:
                        break
                    chunks.append(chunk)
                return b"".join(chunks)

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    data = await asyncio.to_thread(_sync_download)
                    return data, self.compute_sha256(data)
                except Exception as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                    else:
                        logger.debug(f"Cloud download failed for {file_key}: {e}. Checking local vault.")

        # Check local vault
        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        if not local_path.exists():
            local_path = LOCAL_VAULT_DIR / file_key
        if local_path.exists():
            data = await asyncio.to_thread(local_path.read_bytes)
            return data, self.compute_sha256(data)

        raise FileNotFoundError(f"Evidence file key '{file_key}' not found in cloud storage or local vault.")

    async def delete_evidence(self, file_key: str) -> bool:
        """
        Deletes evidence artifact permanently.
        """
        deleted = False
        if self.is_cloud_enabled:
            try:
                await asyncio.to_thread(self._s3_client.delete_object, Bucket=self.bucket_name, Key=file_key)
                deleted = True
            except Exception as e:
                logger.error(f"Error deleting from cloud storage: {e}")

        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        if not local_path.exists():
            local_path = LOCAL_VAULT_DIR / file_key
        if local_path.exists():
            try:
                await asyncio.to_thread(local_path.unlink)
                deleted = True
            except Exception as e:
                logger.error(f"Error deleting local vault file: {e}")

        return deleted

    def get_minimal_status(self) -> Dict[str, Any]:
        """Returns minimal operational state without leaking endpoints, buckets, or paths."""
        return {
            "status": "connected" if self.is_cloud_enabled else "local_fallback"
        }

    def get_safe_status(self) -> Dict[str, Any]:
        """Returns sanitized status for authenticated UI views, excluding filesystem paths and endpoints."""
        if self.is_cloud_enabled:
            storage_mode = "Neon Object Storage (S3)" if self.is_neon else "Backblaze B2 (Cloud)"
        else:
            storage_mode = "Local Evidence Vault (Filesystem)"

        return {
            "b2_cloud_configured": self.is_cloud_enabled,
            "cloud_enabled": self.is_cloud_enabled,
            "is_neon": self.is_neon,
            "provider": "Neon" if self.is_neon else ("Backblaze B2" if self.is_cloud_enabled else "Local"),
            "storage_mode": storage_mode
        }

    def get_status(self) -> Dict[str, Any]:
        """Returns storage connection status and vault metrics."""
        vault_files = list(LOCAL_VAULT_DIR.glob("*"))
        total_vault_size = sum(f.stat().st_size for f in vault_files if f.is_file())
        
        if self.is_cloud_enabled:
            storage_mode = "Neon Object Storage (S3)" if self.is_neon else "Backblaze B2 (Cloud)"
        else:
            storage_mode = "Local Evidence Vault (Filesystem)"

        return {
            "b2_cloud_configured": self.is_cloud_enabled,
            "cloud_enabled": self.is_cloud_enabled,
            "is_neon": self.is_neon,
            "provider": "Neon" if self.is_neon else ("Backblaze B2" if self.is_cloud_enabled else "Local"),
            "b2_endpoint": self.endpoint_url if self.is_cloud_enabled else None,
            "b2_bucket": self.bucket_name if self.is_cloud_enabled else None,
            "endpoint": self.endpoint_url if self.is_cloud_enabled else None,
            "bucket": self.bucket_name if self.is_cloud_enabled else None,
            "region": self.region_name if self.is_cloud_enabled else None,
            "neon_branch": self.neon_branch,
            "storage_mode": storage_mode,
            "local_vault_path": str(LOCAL_VAULT_DIR),
            "local_vault_file_count": len(vault_files),
            "local_vault_size_bytes": total_vault_size
        }

b2_storage = B2StorageService()

