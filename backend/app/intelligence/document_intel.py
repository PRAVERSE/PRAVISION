import re
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("pravision.intelligence.document_intel")

class DocumentIntelligenceEngine:
    """
    Extracts structured OSINT entities and forensic metadata
    from text corpora, documents, and technical files.
    """

    EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    IPV4_REGEX = re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
    DOMAIN_REGEX = re.compile(r'\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}\b')
    BTC_REGEX = re.compile(r'\b(1[a-km-zA-HJ-NP-Z1-9]{25,34}|3[a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-zA-HJ-NP-Z0-9]{25,90})\b')
    ETH_REGEX = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
    CVE_REGEX = re.compile(r'\bCVE-\d{4}-\d{4,7}\b', re.IGNORECASE)
    HASH_SHA256 = re.compile(r'\b[a-fA-F0-9]{64}\b')
    HASH_MD5 = re.compile(r'\b[a-fA-F0-9]{32}\b')

    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """Scans raw text content for observable OSINT identifiers."""
        return {
            "emails": sorted(list(set(self.EMAIL_REGEX.findall(text)))),
            "ip_addresses": sorted(list(set(self.IPV4_REGEX.findall(text)))),
            "domains": sorted(list(set(self.DOMAIN_REGEX.findall(text))))[:50],
            "crypto_wallets": sorted(list(set(self.BTC_REGEX.findall(text) + self.ETH_REGEX.findall(text)))),
            "cves": sorted(list(set(self.CVE_REGEX.findall(text)))),
            "sha256_hashes": sorted(list(set(self.HASH_SHA256.findall(text)))),
            "md5_hashes": sorted(list(set(self.HASH_MD5.findall(text))))
        }

    def inspect_file(self, file_path: str) -> Dict[str, Any]:
        """Reads file, extracts text, and parses forensic metadata."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        extracted_text = ""
        metadata: Dict[str, Any] = {"file_name": os.path.basename(file_path), "file_size": file_size, "extension": ext}

        try:
            if ext in (".txt", ".log", ".csv", ".json", ".md"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    extracted_text = f.read()
            elif ext == ".pdf":
                # Basic string extraction fallback
                with open(file_path, "rb") as f:
                    content = f.read()
                    extracted_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', content.decode("latin-1", errors="ignore"))
            else:
                with open(file_path, "rb") as f:
                    content = f.read()
                    extracted_text = content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")

        entities = self.extract_entities_from_text(extracted_text)

        return {
            "metadata": metadata,
            "text_length": len(extracted_text),
            "discovered_entities": entities
        }

document_intel = DocumentIntelligenceEngine()
