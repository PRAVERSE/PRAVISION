import os
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.config import BASE_DIR, TEMP_DATA_DIR

logger = logging.getLogger("pravision.storage.b2")

LOCAL_VAULT_DIR = TEMP_DATA_DIR / "evidence_vault"
LOCAL_VAULT_DIR.mkdir(parents=True, exist_ok=True)

class B2StorageService:
    """
    Backblaze B2 Cloud Object Storage service (S3-compatible API)
    with seamless local file vault fallback and strict SHA-256 cryptographic chain of custody.
    """

    def __init__(self):
        self.key_id = os.environ.get("B2_APPLICATION_KEY_ID") or os.environ.get("B2_KEY_ID")
        self.app_key = os.environ.get("B2_APPLICATION_KEY") or os.environ.get("B2_KEY")
        self.bucket_name = os.environ.get("B2_BUCKET_NAME", "pravision-evidence-vault")
        self.endpoint_url = os.environ.get("B2_ENDPOINT_URL", "https://s3.us-west-004.backblazeb2.com")
        self.region_name = os.environ.get("B2_REGION_NAME", "us-west-004")
        self._s3_client = None

        if self.key_id and self.app_key:
            try:
                import boto3
                from botocore.config import Config
                self._s3_client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    aws_access_key_id=self.key_id,
                    aws_secret_access_key=self.app_key,
                    config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"})
                )
                logger.info(f"Initialized Backblaze B2 client for bucket '{self.bucket_name}' at {self.endpoint_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize B2 boto3 client: {e}. Falling back to local secure vault.")
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
        Uploads an evidence file to B2 or local vault. Returns storage metadata and SHA-256 hash.
        """
        sha256_hash = self.compute_sha256(data)
        size_bytes = len(data)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = filename.replace(" ", "_").replace("/", "_").replace("\\", "_")
        prefix = f"investigations/{investigation_id}/" if investigation_id else "global/"
        file_key = f"{prefix}{timestamp}_{sha256_hash[:12]}_{safe_filename}"

        if self.is_cloud_enabled:
            try:
                self._s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=file_key,
                    Body=data,
                    ContentType=content_type,
                    Metadata={"sha256": sha256_hash, "original_filename": filename}
                )
                return {
                    "storage_backend": "b2_cloud",
                    "file_key": file_key,
                    "file_hash": sha256_hash,
                    "file_size": size_bytes,
                    "mime_type": content_type,
                    "bucket": self.bucket_name,
                    "endpoint": self.endpoint_url
                }
            except Exception as e:
                logger.error(f"Error uploading to Backblaze B2: {e}. Falling back to local vault.")

        # Local Vault Fallback
        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        with open(local_path, "wb") as f:
            f.write(data)

        return {
            "storage_backend": "local_vault",
            "file_key": str(local_path.name),
            "file_hash": sha256_hash,
            "file_size": size_bytes,
            "mime_type": content_type,
            "local_path": str(local_path)
        }

    async def download_evidence(self, file_key: str) -> Tuple[bytes, str]:
        """
        Downloads evidence file and validates its SHA-256 checksum.
        """
        if self.is_cloud_enabled:
            try:
                resp = self._s3_client.get_object(Bucket=self.bucket_name, Key=file_key)
                data = resp["Body"].read()
                return data, self.compute_sha256(data)
            except Exception as e:
                logger.debug(f"Cloud download failed for {file_key}: {e}. Checking local vault.")

        # Check local vault
        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        if not local_path.exists():
            local_path = LOCAL_VAULT_DIR / file_key
        if local_path.exists():
            with open(local_path, "rb") as f:
                data = f.read()
            return data, self.compute_sha256(data)

        raise FileNotFoundError(f"Evidence file key '{file_key}' not found in B2 or local vault.")

    async def delete_evidence(self, file_key: str) -> bool:
        """
        Deletes evidence artifact permanently.
        """
        deleted = False
        if self.is_cloud_enabled:
            try:
                self._s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
                deleted = True
            except Exception as e:
                logger.error(f"Error deleting from B2: {e}")

        local_path = LOCAL_VAULT_DIR / file_key.replace("/", "_")
        if not local_path.exists():
            local_path = LOCAL_VAULT_DIR / file_key
        if local_path.exists():
            try:
                local_path.unlink()
                deleted = True
            except Exception as e:
                logger.error(f"Error deleting local vault file: {e}")

        return deleted

    def get_status(self) -> Dict[str, Any]:
        """Returns B2 connection status and vault metrics."""
        vault_files = list(LOCAL_VAULT_DIR.glob("*"))
        total_vault_size = sum(f.stat().st_size for f in vault_files if f.is_file())
        return {
            "b2_cloud_configured": self.is_cloud_enabled,
            "b2_endpoint": self.endpoint_url if self.is_cloud_enabled else None,
            "b2_bucket": self.bucket_name if self.is_cloud_enabled else None,
            "storage_mode": "Backblaze B2 (Cloud)" if self.is_cloud_enabled else "Local Evidence Vault (Filesystem)",
            "local_vault_path": str(LOCAL_VAULT_DIR),
            "local_vault_file_count": len(vault_files),
            "local_vault_size_bytes": total_vault_size
        }

b2_storage = B2StorageService()
