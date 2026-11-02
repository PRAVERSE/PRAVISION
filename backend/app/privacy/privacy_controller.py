import os
import shutil
import logging
import re
from pathlib import Path
from typing import Optional
from app.config import settings

logger = logging.getLogger("pravision.privacy")

class PrivacyController:
    """
    Enforces PRAVISION's strict zero-investigation-history mandate:
    1. No persistent target storage.
    2. Zero target identifiers written to disk logs.
    3. Memory-only investigation lifecycle.
    4. Immediate, secure eradication of ephemeral scratch files when an investigation is closed.
    """

    def __init__(self, temp_dir: Optional[Path] = None):
        self.temp_dir = temp_dir or settings.ephemeral_data_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_log_message(self, message: str) -> str:
        """Redacts secrets, emails, and phone numbers from diagnostic logs."""
        # 1. Redact API keys / bearer tokens first
        redacted = re.sub(r'(Bearer\s+|api[-_]?key[:=]\s*)[A-Za-z0-9_\-\.]{12,}', r'\1[REDACTED_SECRET]', message, flags=re.IGNORECASE)
        # 2. Redact emails
        redacted = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[REDACTED_EMAIL]', redacted)
        # 3. Redact phone numbers (with word boundaries)
        redacted = re.sub(r'(?<!\w)\+?[1-9]\d{6,14}(?!\w)', '[REDACTED_PHONE]', redacted)
        return redacted

    def create_ephemeral_file(self, filename: str, content: bytes) -> Path:
        """Writes temporary file needed for media/document processing."""
        safe_path = self.temp_dir / filename
        with open(safe_path, "wb") as f:
            f.write(content)
        return safe_path

    def cleanup_ephemeral_file(self, file_path: Path | str) -> bool:
        """Deletes a temporary file securely."""
        try:
            p = Path(file_path)
            if p.exists() and self.temp_dir in p.parents:
                p.unlink(missing_ok=True)
                return True
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file: {e}")
        return False

    def purge_all_ephemeral_data(self, preserve_file: Optional[Path | str] = None) -> int:
        """Purges all files in the runtime temp directory except optionally preserved target."""
        deleted_count = 0
        if not self.temp_dir.exists():
            return 0

        preserve_path = Path(preserve_file).resolve() if preserve_file else None

        for item in self.temp_dir.glob("*"):
            try:
                if preserve_path and item.resolve() == preserve_path:
                    continue
                if item.is_file():
                    item.unlink(missing_ok=True)
                    deleted_count += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    deleted_count += 1
            except Exception as e:
                logger.error(f"Error purging ephemeral file {item.name}: {e}")
                
        logger.info(f"Purged {deleted_count} ephemeral items from runtime directory.")
        return deleted_count

privacy_controller = PrivacyController()
