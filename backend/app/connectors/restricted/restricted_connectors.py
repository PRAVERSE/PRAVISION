from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType

class SeekerConnector(BaseConnector):
    name = "seeker"
    display_name = "Seeker (Restricted Research Catalogue)"
    category = ToolCategory.RESTRICTED_RESEARCH
    description = "Deceptive geolocation tool using HTML5 geolocation API phishing links."
    website_or_repo = "https://github.com/thewhiteh4t/seeker"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = []
    restricted_capabilities = ["deceptive_camera_capture", "covert_gps_harvesting", "social_engineering_lures"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.RESTRICTED
        self._last_error = "Restricted: Covert GPS extraction and deceptive phishing lures are strictly prohibited by PRAVISION safety policies."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class RFoneConnector(BaseConnector):
    name = "r_fone"
    display_name = "R-Fone (Restricted Research Catalogue)"
    category = ToolCategory.RESTRICTED_RESEARCH
    description = "Phone number intelligence tool featuring intrusive subscriber queries."
    website_or_repo = "https://github.com"
    requires_api_key = False
    supported_entity_types = [EntityType.PHONE]
    capabilities = []
    restricted_capabilities = ["private_subscriber_tracking", "deceptive_sms_lures"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.RESTRICTED
        self._last_error = "Restricted: Intrusive subscriber tracking disabled."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class BashHotConnector(BaseConnector):
    name = "bash_hot"
    display_name = "Bash Hot.sh (Restricted Research Catalogue)"
    category = ToolCategory.RESTRICTED_RESEARCH
    description = "Offensive credential sniffing and phishing framework."
    website_or_repo = "https://github.com"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = []
    restricted_capabilities = ["credential_harvesting", "deceptive_login_portals"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.RESTRICTED
        self._last_error = "Restricted: Credential harvesting and phishing strictly prohibited."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class PimEyesConnector(BaseConnector):
    name = "pimeyes"
    display_name = "PimEyes (Restricted Biometric Search)"
    category = ToolCategory.RESTRICTED_RESEARCH
    description = "Facial recognition search engine and reverse image search mechanism."
    website_or_repo = "https://pimeyes.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IMAGE]
    capabilities = []
    restricted_capabilities = ["biometric_face_recognition", "individual_surveillance_tracking"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.RESTRICTED
        self._last_error = "Restricted: Biometric facial identification of individuals is strictly disabled."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class FaceCheckConnector(BaseConnector):
    name = "facecheck_id"
    display_name = "FaceCheck.ID (Restricted Biometric Search)"
    category = ToolCategory.RESTRICTED_RESEARCH
    description = "Facial recognition search across public web mugshots and social media."
    website_or_repo = "https://facecheck.id"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IMAGE]
    capabilities = []
    restricted_capabilities = ["biometric_face_matching", "facial_indexing"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.RESTRICTED
        self._last_error = "Restricted: Biometric facial indexing is disabled."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

