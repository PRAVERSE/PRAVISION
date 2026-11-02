import httpx
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.security import secret_vault

class ShodanConnector(BaseConnector):
    name = "shodan"
    display_name = "Shodan Search Engine"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Search engine for Internet-connected devices, open ports, banners, and vulnerabilities."
    website_or_repo = "https://www.shodan.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN]
    capabilities = ["banner_inspection", "open_ports_detection", "asn_organization_discovery"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("shodan_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "Shodan API key required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        api_key = secret_vault.get_secret("shodan_api_key")
        if not api_key:
            return findings

        target = request.target_value.strip()
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"https://api.shodan.io/shodan/host/{target}?key={api_key}")
                if resp.status_code == 200:
                    data = resp.json()
                    org = data.get("org", "Unknown Org")
                    asn = data.get("asn", "Unknown ASN")
                    ports = data.get("ports", [])
                    vulns = list(data.get("vulns", []))

                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.ORGANIZATION,
                        entity_value=org,
                        source_name="Shodan Host Engine",
                        source_url=f"https://www.shodan.io/host/{target}",
                        evidence_description=f"ASN: {asn} | Org: {org} | Open Ports: {', '.join(map(str, ports))} | CVEs: {', '.join(vulns[:4]) if vulns else 'None'}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="shodan_verified",
                        raw_payload=data
                    ))
            except Exception as e:
                self._last_error = str(e)

        return findings

class CensysConnector(BaseConnector):
    name = "censys"
    display_name = "Censys Search Engine"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Authoritative continuous visibility into global Internet assets and TLS certificates."
    website_or_repo = "https://censys.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN]
    capabilities = ["tls_transparency_search", "asset_inventory"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("censys_api_id") and secret_vault.has_secret("censys_api_secret"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "Censys API ID and Secret required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class IntelXPlatformConnector(BaseConnector):
    name = "intelx_platform"
    display_name = "Intelligence X Global Archive"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Searches Intelligence X selectors across darknet, public leaks, and documents."
    website_or_repo = "https://intelx.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.DOMAIN, EntityType.EMAIL, EntityType.IP_ADDRESS, EntityType.HASH]
    capabilities = ["selector_cross_correlation", "public_archive_lookup"]
    restricted_capabilities = ["plaintext_password_harvesting"]

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("intelx_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "Intelligence X API key required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class MaltegoConnector(BaseConnector):
    name = "maltego"
    display_name = "Maltego Graph Integration"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Link analysis and data-mining transform adapter supporting standard Maltego MTZ export format."
    website_or_repo = "https://www.maltego.com"
    requires_api_key = False
    is_commercial = True
    supported_entity_types = [EntityType.DOMAIN, EntityType.IP_ADDRESS, EntityType.EMAIL, EntityType.PERSON_NAME]
    capabilities = ["graph_mtz_export_compatibility", "link_analysis_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        self._last_error = "Format exporter active; PRAVISION native graph operates independently."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class SocialLinksConnector(BaseConnector):
    name = "social_links"
    display_name = "Social Links (SL Crimewall)"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Enterprise social intelligence, criminal investigation, and dark web transforms."
    website_or_repo = "https://sociallinks.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.USERNAME, EntityType.EMAIL, EntityType.PHONE]
    capabilities = ["enterprise_social_transforms"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Enterprise license and Social Links API token required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class BabelStreetConnector(BaseConnector):
    name = "babel_street"
    display_name = "Babel Street Analytics"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Multilingual threat intelligence, sanctions screening, and global publicly available information (PAI)."
    website_or_repo = "https://www.babelstreet.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.PERSON_NAME, EntityType.ORGANIZATION]
    capabilities = ["multilingual_pai_screening"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Enterprise Babel Street subscription required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class IBMi2Connector(BaseConnector):
    name = "ibm_i2"
    display_name = "IBM i2 Analyst's Notebook"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Visual analysis tool for intelligence analysis, fraud, and national security data interchange."
    website_or_repo = "https://i2group.com"
    requires_api_key = False
    is_commercial = True
    supported_entity_types = [EntityType.PERSON_NAME, EntityType.ORGANIZATION]
    capabilities = ["anb_exchange_schema_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        self._last_error = "Entity schema compatibility mapping active."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class OSINTFrameworkConnector(BaseConnector):
    name = "osint_framework"
    display_name = "OSINT Framework Tree"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Structured tree navigation mapping open-source intelligence resources by category."
    website_or_repo = "https://osintframework.com"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME, EntityType.EMAIL, EntityType.DOMAIN, EntityType.PHONE]
    capabilities = ["methodology_guidance", "resource_classification"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=f"https://osintframework.com/",
                source_name="OSINT Framework",
                source_url="https://osintframework.com/",
                evidence_description="Referenced OSINT Framework methodology directory for recursive expansion paths",
                match_type=MatchType.STRUCTURAL_MATCH,
                confidence=ConfidenceLevel.HIGH,
                verification_status="methodology_catalog"
            )
        ]

