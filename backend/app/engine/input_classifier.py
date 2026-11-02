import re
import ipaddress
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from app.evidence.models import EntityType

class InvestigationMode(str):
    PUBLIC_IDENTITY = "mode_1_identity"
    MEDIA = "mode_2_media"
    EMAIL = "mode_3_email"
    PHONE = "mode_4_phone"
    WEBSITE_DOMAIN = "mode_5_website_domain"
    ORGANIZATION_ASSET = "mode_6_organization_asset"
    GLOBAL_SITUATIONAL = "mode_7_global_situational"

class ClassifiedInput(BaseModel):
    raw_value: str
    detected_type: EntityType
    mode: str
    is_valid: bool
    recommended_connectors: List[str]
    requires_authorization_confirmation: bool
    authorization_note: Optional[str] = None
    expected_scope: str

class InputClassifier:
    """
    Intelligently analyzes arbitrary user input and maps it to the correct investigation mode,
    permitted connectors, and authorization boundaries.
    """

    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    PHONE_PATTERN = re.compile(r'^\+?[0-9\s\-\(\)\.]{7,20}$')
    URL_PATTERN = re.compile(r'^https?://[^\s/$.?#].[^\s]*$', re.IGNORECASE)
    DOMAIN_PATTERN = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
    COORD_PATTERN = re.compile(r'^[-+]?([1-8]?\d(\.\d+)?|90(\.0+)?),\s*[-+]?(180(\.0+)?|((1[0-7]\d)|([1-9]?\d))(\.\d+)?)$')
    HASH_MD5 = re.compile(r'^[a-fA-F0-9]{32}$')
    HASH_SHA256 = re.compile(r'^[a-fA-F0-9]{64}$')

    MEDIA_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.mp4', '.mov', '.avi', '.wav', '.mp3'}
    DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.doc', '.txt', '.csv', '.xlsx', '.json'}

    def classify(self, raw_input: str) -> ClassifiedInput:
        val = raw_input.strip()

        # 1. Geographic Coordinates Check
        if self.COORD_PATTERN.match(val):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.GEO_COORDINATE,
                mode=InvestigationMode.GLOBAL_SITUATIONAL,
                is_valid=True,
                recommended_connectors=["google_earth", "streetview", "sun_position", "openstreetmap"],
                requires_authorization_confirmation=False,
                expected_scope="Sun solar angle, geographic terrain analysis, satellite imagery, public infrastructure references."
            )

        # 2. Email Check
        if self.EMAIL_PATTERN.match(val):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.EMAIL,
                mode=InvestigationMode.EMAIL,
                is_valid=True,
                recommended_connectors=["ghunt", "hibp", "hunter", "email_hippo", "emailrep", "apollo", "intelx_email"],
                requires_authorization_confirmation=True,
                authorization_note="Authorized audit only. Private account enumeration, password retrieval, or unauthorized credential searches are strictly prohibited.",
                expected_scope="Syntax validation, MX routing, publicly disclosed business profiles, exposure metadata."
            )

        # 3. URL Check
        if self.URL_PATTERN.match(val):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.URL,
                mode=InvestigationMode.WEBSITE_DOMAIN,
                is_valid=True,
                recommended_connectors=["whatweb", "subfinder", "dnsx", "photon", "amass", "bbot", "theharvester"],
                requires_authorization_confirmation=False,
                expected_scope="TLS certificate inspection, DNS mapping, tech stack discovery, HTTP header analysis."
            )

        # 4. IP Address Check
        try:
            ipaddress.ip_address(val)
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.IP_ADDRESS,
                mode=InvestigationMode.ORGANIZATION_ASSET,
                is_valid=True,
                recommended_connectors=["shodan", "censys", "nmap", "spiderfoot", "dnsx"],
                requires_authorization_confirmation=True,
                authorization_note="Only passive analysis is conducted by default. Port scanning or service audits require explicit infrastructure ownership authorization.",
                expected_scope="Passive DNS resolution, autonomous system routing, certificate transparency."
            )
        except ValueError:
            pass

        # 5. File Hashes
        if self.HASH_MD5.match(val) or self.HASH_SHA256.match(val):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.HASH,
                mode=InvestigationMode.ORGANIZATION_ASSET,
                is_valid=True,
                recommended_connectors=["intelx_platform", "spiderfoot"],
                requires_authorization_confirmation=False,
                expected_scope="Cryptographic hash lookup, public malware repository references, file reputation."
            )

        # 6. Domain Name Check
        if self.DOMAIN_PATTERN.match(val):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.DOMAIN,
                mode=InvestigationMode.WEBSITE_DOMAIN,
                is_valid=True,
                recommended_connectors=["subfinder", "dnsx", "amass", "theharvester", "whatweb", "photon", "shodan"],
                requires_authorization_confirmation=False,
                expected_scope="DNS records (A, MX, TXT, NS), subdomain enumeration, certificate transparency, technologies."
            )

        # 7. Phone Number Check
        cleaned_phone = "".join(c for c in val if c.isdigit() or c == '+')
        if (val.startswith('+') and len(cleaned_phone) >= 8 and len(cleaned_phone) <= 16) or (self.PHONE_PATTERN.match(val) and len(cleaned_phone) >= 10):
            return ClassifiedInput(
                raw_value=val,
                detected_type=EntityType.PHONE,
                mode=InvestigationMode.PHONE,
                is_valid=True,
                recommended_connectors=["phoneinfoga", "numverify"],
                requires_authorization_confirmation=False,
                expected_scope="E.164 normalization, carrier identification, country/region classification, public telephone directory references."
            )

        # 8. File / Media / Document by extension in path or string
        lower_val = val.lower()
        for ext in self.MEDIA_EXTENSIONS:
            if lower_val.endswith(ext):
                return ClassifiedInput(
                    raw_value=val,
                    detected_type=EntityType.IMAGE,
                    mode=InvestigationMode.MEDIA,
                    is_valid=True,
                    recommended_connectors=["exiftool", "tineye", "google_images", "google_lens", "yandex", "fotoforensics"],
                    requires_authorization_confirmation=False,
                    expected_scope="EXIF camera metadata extraction, GPS tags, perceptual hash calculation, non-biometric reverse visual similarity."
                )

        for ext in self.DOCUMENT_EXTENSIONS:
            if lower_val.endswith(ext):
                return ClassifiedInput(
                    raw_value=val,
                    detected_type=EntityType.DOCUMENT,
                    mode=InvestigationMode.MEDIA,
                    is_valid=True,
                    recommended_connectors=["exiftool", "metagoofil"],
                    requires_authorization_confirmation=False,
                    expected_scope="Document metadata (author, software, creation timestamp), revision history, embedded links."
                )

        # 9. Username / Handle Default
        clean_user = val.lstrip('@')
        is_valid_user = bool(re.match(r'^[a-zA-Z0-9_\-\.]{2,40}$', clean_user))
        return ClassifiedInput(
            raw_value=clean_user,
            detected_type=EntityType.USERNAME,
            mode=InvestigationMode.PUBLIC_IDENTITY,
            is_valid=is_valid_user,
            recommended_connectors=["sherlock", "maigret", "ghunt", "social_scan", "mister_holmes", "osogram"],
            requires_authorization_confirmation=False,
            expected_scope="Public profile discovery, cross-platform username match analysis, public bio link collection."
        )

input_classifier = InputClassifier()

