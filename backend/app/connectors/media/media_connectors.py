import urllib.parse
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.media_forensics.metadata_extractor import metadata_extractor, hash_calculator
from app.media_forensics.forensic_analyzer import forensic_analyzer

class ExifToolConnector(BaseConnector):
    name = "exiftool"
    display_name = "ExifTool & Media Extractor"
    category = ToolCategory.MEDIA_IMAGE
    description = "Extracts EXIF, XMP, IPTC, GPS coordinate tags, camera equipment, and capture timestamps."
    website_or_repo = "https://exiftool.org"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE, EntityType.DOCUMENT]
    capabilities = [
        "exif_metadata_extraction",
        "gps_coordinate_extraction",
        "camera_hardware_profiling",
        "timestamp_extraction"
    ]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        file_path = request.target_value.strip()

        meta = metadata_extractor.extract(file_path)
        hashes = hash_calculator.calculate(file_path)

        if hashes["sha256"]:
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.HASH,
                entity_value=hashes["sha256"],
                source_name="Media Hash Engine",
                evidence_description=f"SHA-256: {hashes['sha256']} | MD5: {hashes['md5']} | pHash: {hashes['phash']}",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.CORROBORATED,
                verification_status="cryptographic_fingerprint",
                raw_payload=hashes
            ))

        if meta.get("camera_make") or meta.get("camera_model"):
            cam = f"{meta.get('camera_make', '')} {meta.get('camera_model', '')}".strip()
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.TECHNOLOGY,
                entity_value=cam,
                source_name="ExifTool Engine",
                evidence_description=f"Hardware profile: {cam} (Software: {meta.get('software') or 'Default'})",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.HIGH,
                verification_status="metadata_verified"
            ))

        if meta.get("gps_coordinates"):
            lat, lon = meta["gps_coordinates"]
            coord_str = f"{lat}, {lon}"
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.GEO_COORDINATE,
                entity_value=coord_str,
                source_name="ExifTool GPS",
                source_url=f"https://www.google.com/maps?q={lat},{lon}",
                evidence_description=f"Embedded camera GPS coordinates: Latitude {lat}, Longitude {lon}",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.HIGH,
                verification_status="embedded_geotag",
                raw_payload={"latitude": lat, "longitude": lon}
            ))

        return findings

class FotoForensicsConnector(BaseConnector):
    name = "fotoforensics"
    display_name = "FotoForensics & ELA Analyzer"
    category = ToolCategory.MEDIA_IMAGE
    description = "Error Level Analysis, compression artifact detection, and digital manipulation indicators."
    website_or_repo = "https://fotoforensics.com"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE]
    capabilities = ["error_level_analysis", "compression_anomaly_detection"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        file_path = request.target_value.strip()
        ela_res = forensic_analyzer.analyze_ela(file_path)

        if ela_res.get("is_analyzed"):
            return [
                EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.IMAGE,
                    entity_value=ela_res.get("ela_image_filename", "ela_result.png"),
                    source_name="FotoForensics ELA",
                    evidence_description=f"Forensic ELA Analysis completed. {ela_res.get('forensic_notes')}",
                    match_type=MatchType.STRUCTURAL_MATCH,
                    confidence=ConfidenceLevel.HIGH,
                    verification_status="forensically_analyzed",
                    raw_payload=ela_res
                )
            ]
        return []

class GoogleLensConnector(BaseConnector):
    name = "google_lens"
    display_name = "Google Lens & Reverse Image"
    category = ToolCategory.MEDIA_IMAGE
    description = "Reverse image query generation for matching visual entities, landmarks, and source web pages."
    website_or_repo = "https://lens.google.com"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE, EntityType.URL]
    capabilities = ["reverse_image_search_links", "visual_similarity_querying"]
    restricted_capabilities = ["biometric_face_recognition"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        encoded = urllib.parse.quote_plus(target)
        lens_url = f"https://lens.google.com/uploadbyurl?url={encoded}" if target.startswith("http") else "https://lens.google.com"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=lens_url,
                source_name="Google Lens",
                source_url=lens_url,
                evidence_description="Authorized reverse visual search query generated for open web indexing",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="search_query"
            )
        ]

class TinEyeConnector(BaseConnector):
    name = "tineye"
    display_name = "TinEye Reverse Image Search"
    category = ToolCategory.MEDIA_IMAGE
    description = "Reverse image search engine finding exact image duplicates and modified versions across the web."
    website_or_repo = "https://tineye.com"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE, EntityType.URL]
    capabilities = ["exact_image_matching", "image_provenance_tracking"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        encoded = urllib.parse.quote_plus(target)
        tineye_url = f"https://tineye.com/search?url={encoded}" if target.startswith("http") else "https://tineye.com"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=tineye_url,
                source_name="TinEye",
                source_url=tineye_url,
                evidence_description="Exact-match reverse image verification query",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="search_query"
            )
        ]

class YandexImagesConnector(BaseConnector):
    name = "yandex_images"
    display_name = "Yandex Visual Search"
    category = ToolCategory.MEDIA_IMAGE
    description = "Reverse image search with high accuracy on objects, architecture, and international web pages."
    website_or_repo = "https://yandex.com/images"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE, EntityType.URL]
    capabilities = ["landmark_recognition", "non_biometric_visual_matching"]
    restricted_capabilities = ["biometric_tracking"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        url = f"https://yandex.com/images/search?rpt=imageview&url={urllib.parse.quote_plus(target)}" if target.startswith("http") else "https://yandex.com/images/"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=url,
                source_name="Yandex Visual Search",
                source_url=url,
                evidence_description="Reverse visual similarity query targeting global and regional imagery",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="search_query"
            )
        ]

class LensoConnector(BaseConnector):
    name = "lenso"
    display_name = "Lenso.ai Visual Discovery"
    category = ToolCategory.MEDIA_IMAGE
    description = "Visual search engine for landmarks, buildings, places, and duplicate imagery."
    website_or_repo = "https://lenso.ai"
    requires_api_key = False
    supported_entity_types = [EntityType.IMAGE]
    capabilities = ["places_landmarks_matching"]
    restricted_capabilities = ["biometric_surveillance"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class SocialCatfishConnector(BaseConnector):
    name = "social_catfish"
    display_name = "Social Catfish (Non-Biometric)"
    category = ToolCategory.MEDIA_IMAGE
    description = "Public verification service for images and profiles."
    website_or_repo = "https://socialcatfish.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IMAGE]
    capabilities = ["public_source_verification"]
    restricted_capabilities = ["biometric_person_tracking"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Commercial subscription required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []
