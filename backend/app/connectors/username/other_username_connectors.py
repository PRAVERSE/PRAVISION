import urllib.parse
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class MisterHolmesConnector(BaseConnector):
    name = "mister_holmes"
    display_name = "Mister Holmes"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Information gathering tool on target handles, discovering public social presence."
    website_or_repo = "https://github.com/lucksi/MisterHolmes"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["public_social_footprinting"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip().lstrip('@')
        # Returns public dossier search reference
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(f'inurl:{target} | intext:\"{target}\"')}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=search_url,
                source_name="Mister Holmes",
                source_url=search_url,
                evidence_description=f"Generated indexed footprint search for '{target}'",
                match_type=MatchType.HEURISTIC_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="search_reference"
            )
        ]

class EyeOfGodConnector(BaseConnector):
    name = "eye_of_god"
    display_name = "Eye of God (Public OSINT)"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Public Russian and CIS open-source search aggregator for public records."
    website_or_repo = "https://t.me/EyeOfGodBot"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.USERNAME, EntityType.PHONE]
    capabilities = ["public_cis_registry_search"]
    restricted_capabilities = ["private_db_lookup"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Commercial subscription and verified bot token required. Restricted to non-private records."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class OsogramConnector(BaseConnector):
    name = "osogram"
    display_name = "Osogram"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Analyzes public Instagram and Telegram profiles without requiring authenticated session credentials."
    website_or_repo = "https://github.com/D4Vinci/Cr3dOv3r"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["public_instagram_discovery", "public_telegram_discovery"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        username = request.target_value.strip().lstrip('@')
        tg_url = f"https://t.me/{username}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=tg_url,
                source_name="Osogram",
                source_url=tg_url,
                evidence_description=f"Public Telegram handle channel/profile discovery target",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="active_handle"
            )
        ]

class InflactConnector(BaseConnector):
    name = "inflact"
    display_name = "Inflact Public Viewer"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Public web viewer for publicly accessible Instagram accounts."
    website_or_repo = "https://inflact.com"
    requires_api_key = False
    is_commercial = True
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["public_instagram_viewer_metadata"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        username = request.target_value.strip().lstrip('@')
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=f"https://inflact.com/profiles/instagram-viewer/{username}/",
                source_name="Inflact",
                evidence_description="Public web viewer reference for public posts",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="web_reference"
            )
        ]

class StalkScanConnector(BaseConnector):
    name = "stalkscan"
    display_name = "StalkScan (Permitted Public Queries Only)"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Generates targeted queries for Facebook's publicly disclosed posts, tags, and photos."
    website_or_repo = "https://stalkscan.com"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["public_facebook_query_generation"]
    restricted_capabilities = ["private_activity_tracking", "friend_graph_scraping"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        encoded = urllib.parse.quote_plus(target)
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=f"https://www.facebook.com/search/posts/?q={encoded}",
                source_name="StalkScan",
                evidence_description="Authorized public Facebook post search filter",
                match_type=MatchType.HEURISTIC_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="public_query_target"
            )
        ]

class FacebookSearchConnector(BaseConnector):
    name = "facebook_public_search"
    display_name = "Public Facebook Search"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Searches publicly indexed Facebook pages, verified public figures, and open public groups."
    website_or_repo = "https://www.facebook.com"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME, EntityType.PERSON_NAME]
    capabilities = ["public_page_discovery", "public_event_discovery"]
    restricted_capabilities = ["private_profile_extraction"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        query = urllib.parse.quote_plus(request.target_value.strip())
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=f"https://www.facebook.com/search/pages/?q={query}",
                source_name="Facebook Public Search",
                evidence_description=f"Public Facebook business page search for '{request.target_value}'",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="public_index_reference"
            )
        ]

