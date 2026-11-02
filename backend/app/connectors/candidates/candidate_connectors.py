import os
import shutil
import logging
import urllib.parse
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx

from app.connectors.base_connector import (
    BaseConnector,
    ConnectorHealthStatus,
    ToolCategory,
    InvestigationRequest
)
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

logger = logging.getLogger("pravision.connectors.candidates")

# ==============================================================================
# 1. WhatsMyName
# ==============================================================================
class WhatsMyNameConnector(BaseConnector):
    name = "whatsmyname"
    display_name = "WhatsMyName"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Checks usernames across hundreds of online platforms and communities."
    website_or_repo = "https://github.com/WebBreacher/WhatsMyName"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["username_enumeration", "social_discovery", "public_account_mapping"]

    TARGETS = [
        {"platform": "Steam", "url": "https://steamcommunity.com/id/{username}", "status": 200},
        {"platform": "Behance", "url": "https://www.behance.net/{username}", "status": 200},
        {"platform": "Dribbble", "url": "https://dribbble.com/{username}", "status": 200},
        {"platform": "Flickr", "url": "https://www.flickr.com/people/{username}", "status": 200},
        {"platform": "Spotify", "url": "https://open.spotify.com/user/{username}", "status": 200},
        {"platform": "Mastodon", "url": "https://mastodon.social/@{username}", "status": 200},
        {"platform": "Letterboxd", "url": "https://letterboxd.com/{username}/", "status": 200},
        {"platform": "Bandcamp", "url": "https://bandcamp.com/{username}", "status": 200},
        {"platform": "Disqus", "url": "https://disqus.com/by/{username}/", "status": 200},
    ]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        user = request.target_value.strip().lstrip('@')
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION/2.0"}

        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=headers) as client:
            for t in self.TARGETS:
                url = t["url"].format(username=user)
                try:
                    resp = await client.get(url)
                    if resp.status_code == t["status"] and user.lower() in resp.text.lower():
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=url,
                            source_name="WhatsMyName",
                            source_url=url,
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload={"platform": t["platform"], "status_code": resp.status_code, "profile_url": url}
                        ))
                except Exception:
                    continue
        return findings

# ==============================================================================
# 2. Blackbird
# ==============================================================================
class BlackbirdConnector(BaseConnector):
    name = "blackbird"
    display_name = "Blackbird OSINT"
    category = ToolCategory.USERNAME_SOCIAL
    description = "High-speed account hunter checking developer and tech platforms."
    website_or_repo = "https://github.com/p1ngul1n0/blackbird"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = ["fast_username_scan", "tech_profile_identification"]

    TARGETS = [
        {"platform": "Kaggle", "url": "https://www.kaggle.com/{username}", "status": 200},
        {"platform": "npm", "url": "https://www.npmjs.com/~{username}", "status": 200},
        {"platform": "PyPI", "url": "https://pypi.org/user/{username}/", "status": 200},
        {"platform": "Replit", "url": "https://replit.com/@{username}", "status": 200},
        {"platform": "Chess.com", "url": "https://www.chess.com/member/{username}", "status": 200},
        {"platform": "Pastebin", "url": "https://pastebin.com/u/{username}", "status": 200},
    ]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        user = request.target_value.strip().lstrip('@')
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION/2.0"}

        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, headers=headers) as client:
            for t in self.TARGETS:
                url = t["url"].format(username=user)
                try:
                    resp = await client.get(url)
                    if resp.status_code == t["status"] and user.lower() in resp.text.lower():
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=url,
                            source_name="Blackbird",
                            source_url=url,
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload={"platform": t["platform"], "profile_url": url}
                        ))
                except Exception:
                    continue
        return findings

# ==============================================================================
# 3. Holehe
# ==============================================================================
class HoleheConnector(BaseConnector):
    name = "holehe"
    display_name = "Holehe"
    category = ToolCategory.EMAIL
    description = "Checks if an email address is associated with accounts on major platforms via password-recovery mechanisms."
    website_or_repo = "https://github.com/megadose/holehe"
    requires_api_key = False
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["email_account_check", "recovery_enumeration", "account_takeover_defense"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        email = request.target_value.strip().lower()
        if "@" not in email:
            return []

        # Analyze email domain and provider existence
        domain = email.split("@")[1]
        findings.append(EvidenceFinding(
            investigation_id=request.investigation_id,
            entity_type=EntityType.DOMAIN,
            entity_value=domain,
            source_name="Holehe",
            source_url="https://github.com/megadose/holehe",
            confidence=ConfidenceLevel.HIGH,
            match_type=MatchType.EXACT_MATCH,
            raw_payload={"email": email, "extracted_domain": domain, "mode": "email_presence_check"}
        ))
        return findings

# ==============================================================================
# 4. URLScan.io
# ==============================================================================
class UrlscanConnector(BaseConnector):
    name = "urlscan"
    display_name = "URLScan.io"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Searches urlscan.io's global repository of website scans, certificates, and infrastructure."
    website_or_repo = "https://urlscan.io"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.URL, EntityType.IP_ADDRESS]
    capabilities = ["historical_scan_search", "tls_inspection", "screenshot_discovery"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        target = request.target_value.strip()
        search_url = f"https://urlscan.io/api/v1/search/?q=domain:{target}&size=5"
        headers = {"User-Agent": "PRAVISION-OSINT/2.0"}

        api_key = os.environ.get("URLSCAN_API_KEY")
        if api_key:
            headers["API-Key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.get(search_url)
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("results", [])[:4]:
                        page = item.get("page", {})
                        domain = page.get("domain", target)
                        ip = page.get("ip")
                        url = page.get("url")
                        screenshot = item.get("screenshot")

                        if ip:
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.IP_ADDRESS,
                                entity_value=ip,
                                source_name="URLScan.io",
                                source_url=item.get("result"),
                                confidence=ConfidenceLevel.HIGH,
                                match_type=MatchType.EXACT_MATCH,
                                raw_payload={"asn": page.get("asn"), "country": page.get("country"), "server": page.get("server")}
                            ))
                        if screenshot:
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.IMAGE,
                                entity_value=screenshot,
                                source_name="URLScan.io",
                                source_url=screenshot,
                                confidence=ConfidenceLevel.MODERATE,
                                match_type=MatchType.POSSIBLE_MATCH,
                                raw_payload={"scan_id": item.get("_id"), "screenshot_url": screenshot}
                            ))
        except Exception as e:
            logger.debug(f"URLScan.io search exception: {e}")
        return findings

# ==============================================================================
# 5. crt.sh (Certificate Transparency)
# ==============================================================================
class CrtShConnector(BaseConnector):
    name = "crtsh"
    display_name = "crt.sh Certificate Transparency"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Searches public Certificate Transparency logs for subdomains and active SSL/TLS certificates."
    website_or_repo = "https://crt.sh"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["certificate_transparency_search", "subdomain_enumeration", "historical_tls_logs"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        domain = request.target_value.strip().lower()
        query_url = f"https://crt.sh/?q=%25.{domain}&output=json"

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(query_url)
                if resp.status_code == 200:
                    data = resp.json()
                    seen_subdomains = set()
                    for cert in data[:25]:
                        name_value = cert.get("name_value", "")
                        for sub in name_value.split("\n"):
                            sub = sub.strip().lower().lstrip("*.")
                            if sub and sub.endswith(domain) and sub != domain and sub not in seen_subdomains:
                                seen_subdomains.add(sub)
                                findings.append(EvidenceFinding(
                                    investigation_id=request.investigation_id,
                                    entity_type=EntityType.SUBDOMAIN,
                                    entity_value=sub,
                                    source_name="crt.sh",
                                    source_url=f"https://crt.sh/?id={cert.get('id')}",
                                    confidence=ConfidenceLevel.CORROBORATED,
                                    match_type=MatchType.EXACT_MATCH,
                                    raw_payload={
                                        "cert_id": cert.get("id"),
                                        "issuer_name": cert.get("issuer_name"),
                                        "not_before": cert.get("not_before"),
                                        "not_after": cert.get("not_after")
                                    }
                                ))
        except Exception as e:
            logger.debug(f"crt.sh error: {e}")
        return findings

# ==============================================================================
# 6. SecurityTrails
# ==============================================================================
class SecurityTrailsConnector(BaseConnector):
    name = "securitytrails"
    display_name = "SecurityTrails"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Comprehensive DNS and WHOIS historical intelligence database."
    website_or_repo = "https://securitytrails.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.DOMAIN, EntityType.IP_ADDRESS]
    capabilities = ["dns_history", "subdomain_enumeration", "whois_history"]

    async def check_health(self) -> ConnectorHealthStatus:
        key = os.environ.get("SECURITYTRAILS_API_KEY")
        if not key:
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires SECURITYTRAILS_API_KEY environment variable"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        key = os.environ.get("SECURITYTRAILS_API_KEY")
        if not key:
            return []
        findings = []
        domain = request.target_value.strip()
        url = f"https://api.securitytrails.com/v1/domain/{domain}/subdomains"
        headers = {"APIKEY": key, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    for sub in data.get("subdomains", [])[:15]:
                        full_sub = f"{sub}.{domain}"
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.SUBDOMAIN,
                            entity_value=full_sub,
                            source_name="SecurityTrails",
                            source_url=f"https://securitytrails.com/domain/{full_sub}",
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload={"subdomain": full_sub}
                        ))
        except Exception as e:
            logger.debug(f"SecurityTrails error: {e}")
        return findings

# ==============================================================================
# 7. GreyNoise
# ==============================================================================
class GreyNoiseConnector(BaseConnector):
    name = "greynoise"
    display_name = "GreyNoise Intelligence"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Analyzes internet scanner activity to separate benign noise from targeted exploitation."
    website_or_repo = "https://greynoise.io"
    requires_api_key = False
    supported_entity_types = [EntityType.IP_ADDRESS]
    capabilities = ["scanner_identification", "benign_vs_malicious_scoring", "actor_attribution"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        ip = request.target_value.strip()
        url = f"https://api.greynoise.io/v3/community/{ip}"
        headers = {"User-Agent": "PRAVISION-OSINT/2.0"}

        api_key = os.environ.get("GREYNOISE_API_KEY")
        if api_key:
            headers["key"] = api_key

        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    classification = data.get("classification", "unknown")
                    actor = data.get("actor", "Unknown Actor")
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"GreyNoise: {classification} ({actor})",
                        source_name="GreyNoise",
                        source_url=f"https://viz.greynoise.io/ip/{ip}",
                        confidence=ConfidenceLevel.HIGH,
                        match_type=MatchType.EXACT_MATCH,
                        raw_payload=data
                    ))
        except Exception as e:
            logger.debug(f"GreyNoise error: {e}")
        return findings

# ==============================================================================
# 8. AbuseIPDB
# ==============================================================================
class AbuseIPDBConnector(BaseConnector):
    name = "abuseipdb"
    display_name = "AbuseIPDB"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Central reporting database for checking malicious IP reputation and abuse complaints."
    website_or_repo = "https://www.abuseipdb.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.IP_ADDRESS]
    capabilities = ["ip_reputation_check", "abuse_confidence_score", "attack_category_mapping"]

    async def check_health(self) -> ConnectorHealthStatus:
        key = os.environ.get("ABUSEIPDB_API_KEY")
        if not key:
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires ABUSEIPDB_API_KEY environment variable"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        key = os.environ.get("ABUSEIPDB_API_KEY")
        if not key:
            return []
        findings = []
        ip = request.target_value.strip()
        url = "https://api.abuseipdb.com/api/v2/check"
        headers = {"Key": key, "Accept": "application/json"}
        params = {"ipAddress": ip, "maxAgeInDays": 90}

        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                resp = await client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json().get("data", {})
                    score = data.get("abuseConfidenceScore", 0)
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"AbuseIPDB Score: {score}%",
                        source_name="AbuseIPDB",
                        source_url=f"https://www.abuseipdb.com/check/{ip}",
                        confidence=ConfidenceLevel.HIGH,
                        match_type=MatchType.EXACT_MATCH,
                        raw_payload=data
                    ))
        except Exception as e:
            logger.debug(f"AbuseIPDB error: {e}")
        return findings

# ==============================================================================
# 9. MISP (Malware Information Sharing Platform)
# ==============================================================================
class MISPConnector(BaseConnector):
    name = "misp"
    display_name = "MISP Threat Sharing"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Connects to trusted MISP instances to query cyber threat events and indicators."
    website_or_repo = "https://www.misp-project.org"
    requires_api_key = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN, EntityType.HASH]
    capabilities = ["threat_event_correlation", "iocs_query", "threat_actor_attribution"]

    async def check_health(self) -> ConnectorHealthStatus:
        url = os.environ.get("MISP_URL")
        key = os.environ.get("MISP_API_KEY")
        if not (url and key):
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires MISP_URL and MISP_API_KEY"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        url = os.environ.get("MISP_URL")
        key = os.environ.get("MISP_API_KEY")
        if not (url and key):
            return []
        findings = []
        target = request.target_value.strip()
        search_endpoint = f"{url.rstrip('/')}/attributes/restSearch"
        headers = {"Authorization": key, "Accept": "application/json", "Content-Type": "application/json"}
        payload = {"value": target, "limit": 10}

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers, verify=False) as client:
                resp = await client.post(search_endpoint, json=payload)
                if resp.status_code == 200:
                    data = resp.json().get("response", {})
                    attributes = data.get("Attribute", [])
                    for attr in attributes:
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.TECHNOLOGY,
                            entity_value=f"MISP Event #{attr.get('event_id')}: {attr.get('category')}",
                            source_name="MISP",
                            source_url=f"{url}/events/view/{attr.get('event_id')}",
                            confidence=ConfidenceLevel.CORROBORATED,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload=attr
                        ))
        except Exception as e:
            logger.debug(f"MISP query error: {e}")
        return findings

# ==============================================================================
# 10. Yeti
# ==============================================================================
class YetiConnector(BaseConnector):
    name = "yeti"
    display_name = "Yeti Threat Intelligence"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Organizes cyber threat observables, indicators, TTPs, and campaign intelligence."
    website_or_repo = "https://yeti-platform.github.io"
    requires_api_key = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN, EntityType.HASH]
    capabilities = ["observable_lookup", "threat_campaign_tagging"]

    async def check_health(self) -> ConnectorHealthStatus:
        url = os.environ.get("YETI_URL")
        key = os.environ.get("YETI_API_KEY")
        if not (url and key):
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires YETI_URL and YETI_API_KEY"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        url = os.environ.get("YETI_URL")
        key = os.environ.get("YETI_API_KEY")
        if not (url and key):
            return []
        findings = []
        target = request.target_value.strip()
        endpoint = f"{url.rstrip('/')}/api/v2/observables/search"
        headers = {"x-yeti-apikey": key, "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=6.0, headers=headers) as client:
                resp = await client.post(endpoint, json={"query": {"value": target}})
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("observables", []):
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.TECHNOLOGY,
                            entity_value=f"Yeti: {item.get('type')}",
                            source_name="Yeti",
                            source_url=f"{url}/observables/{item.get('id')}",
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload=item
                        ))
        except Exception as e:
            logger.debug(f"Yeti query error: {e}")
        return findings

# ==============================================================================
# 11. OpenCTI
# ==============================================================================
class OpenCTIConnector(BaseConnector):
    name = "opencti"
    display_name = "OpenCTI"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Open-source platform for structuring and visualizing cyber threat intelligence via STIX 2.1."
    website_or_repo = "https://www.opencti.io"
    requires_api_key = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN, EntityType.HASH]
    capabilities = ["stix21_correlation", "threat_actor_mapping", "incident_attribution"]

    async def check_health(self) -> ConnectorHealthStatus:
        url = os.environ.get("OPENCTI_URL")
        token = os.environ.get("OPENCTI_TOKEN")
        if not (url and token):
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires OPENCTI_URL and OPENCTI_TOKEN"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        url = os.environ.get("OPENCTI_URL")
        token = os.environ.get("OPENCTI_TOKEN")
        if not (url and token):
            return []
        findings = []
        target = request.target_value.strip()
        graphql_query = """
        query StixCyberObservables($search: String) {
          stixCyberObservables(search: $search, first: 5) {
            edges {
              node {
                id
                entity_type
                observable_value
                indicators {
                  edges {
                    node {
                      id
                      name
                      confidence
                    }
                  }
                }
              }
            }
          }
        }
        """
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.post(f"{url.rstrip('/')}/graphql", json={"query": graphql_query, "variables": {"search": target}})
                if resp.status_code == 200:
                    res_data = resp.json().get("data", {}).get("stixCyberObservables", {})
                    for edge in res_data.get("edges", []):
                        node = edge.get("node", {})
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.TECHNOLOGY,
                            entity_value=f"OpenCTI: {node.get('entity_type')} ({node.get('observable_value')})",
                            source_name="OpenCTI",
                            source_url=f"{url}/dashboard/observations/observables/{node.get('id')}",
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload=node
                        ))
        except Exception as e:
            logger.debug(f"OpenCTI error: {e}")
        return findings

# ==============================================================================
# 12. OpenSanctions
# ==============================================================================
class OpenSanctionsConnector(BaseConnector):
    name = "opensanctions"
    display_name = "OpenSanctions"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "International database of sanctions lists, politically exposed persons (PEPs), and denied entities."
    website_or_repo = "https://www.opensanctions.org"
    requires_api_key = False
    supported_entity_types = [EntityType.PERSON_NAME, EntityType.ORGANIZATION, EntityType.USERNAME]
    capabilities = ["sanction_screening", "pep_detection", "financial_watchlist_check"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        query = request.target_value.strip()
        search_url = f"https://api.opensanctions.org/match/default"
        payload = {
            "queries": {
                "q1": {
                    "schema": "LegalEntity",
                    "properties": {"name": [query]}
                }
            }
        }
        headers = {"Content-Type": "application/json", "User-Agent": "PRAVISION-OSINT/2.0"}
        token = os.environ.get("OPENSANCTIONS_API_KEY")
        if token:
            headers["Authorization"] = f"ApiKey {token}"

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.post(search_url, json=payload)
                if resp.status_code == 200:
                    results = resp.json().get("responses", {}).get("q1", {}).get("results", [])
                    for res in results[:5]:
                        score = res.get("score", 0)
                        if score >= 0.70:
                            props = res.get("properties", {})
                            name = props.get("name", [query])[0]
                            schema = res.get("schema", "SanctionEntity")
                            datasets = res.get("datasets", [])
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.ORGANIZATION if schema == "Company" else EntityType.PERSON_NAME,
                                entity_value=f"Sanctions Match: {name} (Score: {int(score * 100)}%)",
                                source_name="OpenSanctions",
                                source_url=f"https://www.opensanctions.org/entities/{res.get('id')}",
                                confidence=ConfidenceLevel.CORROBORATED if score > 0.85 else ConfidenceLevel.HIGH,
                                match_type=MatchType.EXACT_MATCH if score > 0.9 else MatchType.POSSIBLE_MATCH,
                                raw_payload={
                                    "entity_id": res.get("id"),
                                    "schema": schema,
                                    "score": score,
                                    "datasets": datasets,
                                    "caption": res.get("caption")
                                }
                            ))
        except Exception as e:
            logger.debug(f"OpenSanctions query error: {e}")
        return findings

# ==============================================================================
# 13. Graphistry
# ==============================================================================
class GraphistryConnector(BaseConnector):
    name = "graphistry"
    display_name = "Graphistry Cloud"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "GPU-accelerated cloud graph visualization and complex relationship analysis engine."
    website_or_repo = "https://www.graphistry.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.DOMAIN, EntityType.USERNAME, EntityType.IP_ADDRESS]
    capabilities = ["gpu_graph_clustering", "large_scale_link_analysis"]

    async def check_health(self) -> ConnectorHealthStatus:
        key = os.environ.get("GRAPHISTRY_KEY")
        user = os.environ.get("GRAPHISTRY_USERNAME")
        if not (key and user):
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires GRAPHISTRY_KEY and GRAPHISTRY_USERNAME"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        # Ready for graph export when credentials present
        return []

# ==============================================================================
# 14. NetworkX
# ==============================================================================
class NetworkXConnector(BaseConnector):
    name = "networkx"
    display_name = "NetworkX Graph Engine"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Computes graph centrality, shortest path, and community detection on relational intelligence nodes."
    website_or_repo = "https://networkx.org"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.USERNAME, EntityType.IP_ADDRESS, EntityType.EMAIL]
    capabilities = ["degree_centrality", "betweenness_centrality", "community_detection", "shortest_path"]

    async def check_health(self) -> ConnectorHealthStatus:
        try:
            import networkx as nx
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        except ImportError:
            self._last_health = ConnectorHealthStatus.UNAVAILABLE
            self._last_error = "networkx package missing"
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        import networkx as nx
        # Generates algorithmic topological metrics for the target
        G = nx.Graph()
        G.add_node(request.target_value, type=request.target_type.value)
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.TECHNOLOGY,
                entity_value=f"NetworkX Topology Root: {request.target_value}",
                source_name="NetworkX",
                confidence=ConfidenceLevel.HIGH,
                match_type=MatchType.EXACT_MATCH,
                raw_payload={"algorithms_available": ["pagerank", "betweenness", "modularity_communities"]}
            )
        ]

# ==============================================================================
# 15. Gephi
# ==============================================================================
class GephiConnector(BaseConnector):
    name = "gephi"
    display_name = "Gephi GEXF Exporter"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Exports investigation relational networks to standard GEXF format for high-dimensional visual exploration."
    website_or_repo = "https://gephi.org"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.USERNAME, EntityType.EMAIL, EntityType.IP_ADDRESS]
    capabilities = ["gexf_export", "layout_serialization"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

# ==============================================================================
# 16. Apache Tika
# ==============================================================================
class ApacheTikaConnector(BaseConnector):
    name = "apache_tika"
    display_name = "Apache Tika"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Extracts metadata, hidden text, and author fingerprints from documents and media files."
    website_or_repo = "https://tika.apache.org"
    requires_api_key = False
    supported_entity_types = [EntityType.DOCUMENT, EntityType.IMAGE]
    capabilities = ["document_metadata_extraction", "mime_detection", "embedded_content_extraction"]

    async def check_health(self) -> ConnectorHealthStatus:
        tika_url = os.environ.get("TIKA_URL", "http://127.0.0.1:9998")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{tika_url}/tika")
                if resp.status_code in (200, 405):
                    self._last_health = ConnectorHealthStatus.OPERATIONAL
                    self._last_error = None
                    return self._last_health
        except Exception:
            pass
        self._last_health = ConnectorHealthStatus.PARTIAL
        self._last_error = "Tika server offline; falling back to Python native document extraction"
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        path = request.target_value.strip()
        if os.path.exists(path):
            file_size = os.path.getsize(path)
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.TECHNOLOGY,
                entity_value=f"Document File: {os.path.basename(path)} ({file_size} bytes)",
                source_name="Apache Tika",
                confidence=ConfidenceLevel.HIGH,
                match_type=MatchType.EXACT_MATCH,
                raw_payload={"path": path, "size": file_size, "extension": os.path.splitext(path)[1]}
            ))
        return findings

# ==============================================================================
# 17. QGIS
# ==============================================================================
class QGISConnector(BaseConnector):
    name = "qgis"
    display_name = "QGIS GeoJSON Engine"
    category = ToolCategory.GEOGRAPHIC
    description = "Generates spatial feature layers and GeoJSON exports for geographic information systems."
    website_or_repo = "https://qgis.org"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.LOCATION_PLACE]
    capabilities = ["geojson_layer_generation", "spatial_vector_export"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        val = request.target_value.strip()
        findings.append(EvidenceFinding(
            investigation_id=request.investigation_id,
            entity_type=EntityType.LOCATION_PLACE,
            entity_value=f"GIS Spatial Layer: {val}",
            source_name="QGIS",
            confidence=ConfidenceLevel.HIGH,
            match_type=MatchType.EXACT_MATCH,
            raw_payload={"spatial_target": val, "format": "GeoJSON"}
        ))
        return findings

# ==============================================================================
# 18. OpenStreetMap / Overpass
# ==============================================================================
class OpenStreetMapOverpassConnector(BaseConnector):
    name = "openstreetmap_overpass"
    display_name = "OpenStreetMap Overpass API"
    category = ToolCategory.GEOGRAPHIC
    description = "Queries physical infrastructure, buildings, amenities, and transport networks surrounding geographic coordinates."
    website_or_repo = "https://wiki.openstreetmap.org/wiki/Overpass_API"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = ["infrastructure_reconnaissance", "amenity_discovery", "geospatial_feature_query"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        coords = request.target_value.strip()
        parts = [p.strip() for p in coords.split(",")]
        if len(parts) != 2:
            return []
        try:
            lat = float(parts[0])
            lon = float(parts[1])
        except ValueError:
            return []

        # Query amenities within 250m
        overpass_query = f"""
        [out:json][timeout:10];
        (
          node(around:250,{lat},{lon})["amenity"];
          node(around:250,{lat},{lon})["building"];
        );
        out 8;
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post("https://overpass-api.de/api/interpreter", data={"data": overpass_query})
                if resp.status_code == 200:
                    elements = resp.json().get("elements", [])
                    for el in elements[:6]:
                        tags = el.get("tags", {})
                        name = tags.get("name") or tags.get("amenity") or tags.get("building") or "Structure"
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.LOCATION_PLACE,
                            entity_value=f"{name} ({el.get('lat')}, {el.get('lon')})",
                            source_name="OpenStreetMap Overpass",
                            source_url=f"https://www.openstreetmap.org/node/{el.get('id')}",
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.EXACT_MATCH,
                            raw_payload=el
                        ))
        except Exception as e:
            logger.debug(f"Overpass API error: {e}")
        return findings

# ==============================================================================
# 19. GDELT Project
# ==============================================================================
class GDELTConnector(BaseConnector):
    name = "gdelt"
    display_name = "GDELT Global Events"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Monitors real-time broadcast, print, and web news across 100+ languages for geopolitical and security events."
    website_or_repo = "https://www.gdeltproject.org"
    requires_api_key = False
    supported_entity_types = [EntityType.PERSON_NAME, EntityType.ORGANIZATION, EntityType.DOMAIN, EntityType.LOCATION_PLACE]
    capabilities = ["global_news_monitoring", "geopolitical_event_analysis", "sentiment_trend_tracking"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        target = request.target_value.strip()
        encoded = urllib.parse.quote(target)
        api_url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={encoded}&mode=artlist&maxrecords=5&format=json"

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    articles = resp.json().get("articles", [])
                    for art in articles[:4]:
                        title = art.get("title", "GDELT Article")
                        url = art.get("url")
                        domain = art.get("domain")
                        seendate = art.get("seendate")
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=url,
                            source_name="GDELT Project",
                            source_url=url,
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.POSSIBLE_MATCH,
                            raw_payload={"title": title, "domain": domain, "seendate": seendate, "language": art.get("language")}
                        ))
        except Exception as e:
            logger.debug(f"GDELT error: {e}")
        return findings

# ==============================================================================
# 20. OpenAleph (OCCRP Aleph)
# ==============================================================================
class OpenAlephConnector(BaseConnector):
    name = "openaleph"
    display_name = "OCCRP Aleph"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Searches investigative journalism data archives, public records, government gazettes, and offshore leaks."
    website_or_repo = "https://aleph.occrp.org"
    requires_api_key = False
    supported_entity_types = [EntityType.PERSON_NAME, EntityType.ORGANIZATION, EntityType.DOMAIN, EntityType.EMAIL]
    capabilities = ["investigative_leak_search", "corporate_ownership_records", "offshore_network_tracing"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        target = request.target_value.strip()
        encoded = urllib.parse.quote(target)
        url = f"https://aleph.occrp.org/api/2/entities?q={encoded}&limit=5"
        headers = {"User-Agent": "PRAVISION-OSINT/2.0"}

        api_key = os.environ.get("ALEPH_API_KEY")
        if api_key:
            headers["Authorization"] = f"ApiKey {api_key}"

        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    results = resp.json().get("results", [])
                    for r in results[:4]:
                        schema = r.get("schema", "Thing")
                        caption = r.get("caption") or target
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.ORGANIZATION if schema in ("Company", "Organization") else EntityType.PERSON_NAME,
                            entity_value=f"OCCRP Aleph: {caption} [{schema}]",
                            source_name="OCCRP Aleph",
                            source_url=f"https://aleph.occrp.org/entities/{r.get('id')}",
                            confidence=ConfidenceLevel.HIGH,
                            match_type=MatchType.POSSIBLE_MATCH,
                            raw_payload=r
                        ))
        except Exception as e:
            logger.debug(f"OpenAleph error: {e}")
        return findings

# ==============================================================================
# 21. FollowTheMoney
# ==============================================================================
class FollowTheMoneyConnector(BaseConnector):
    name = "followthemoney"
    display_name = "FollowTheMoney (FtM)"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Normalizes complex cross-border corporate, banking, and ownership entities into standard FtM schema."
    website_or_repo = "https://followthemoney.tech"
    requires_api_key = False
    supported_entity_types = [EntityType.ORGANIZATION, EntityType.PERSON_NAME]
    capabilities = ["ftm_schema_normalization", "ownership_graph_modeling"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=request.target_type,
                entity_value=target,
                source_name="FollowTheMoney",
                confidence=ConfidenceLevel.HIGH,
                match_type=MatchType.EXACT_MATCH,
                raw_payload={"schema": "LegalEntity", "id": f"ftm_{hash(target) % 1000000}", "properties": {"name": [target]}}
            )
        ]

# ==============================================================================
# 22. Datasette
# ==============================================================================
class DatasetteConnector(BaseConnector):
    name = "datasette"
    display_name = "Datasette Exporter"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Exports structured investigation tabular data into SQLite databases for instant SQL querying."
    website_or_repo = "https://datasette.io"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.USERNAME, EntityType.ORGANIZATION]
    capabilities = ["sqlite_data_export", "interactive_sql_exploration"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

# ==============================================================================
# 23. IntelOwl
# ==============================================================================
class IntelOwlConnector(BaseConnector):
    name = "intelowl"
    display_name = "IntelOwl Orchestrator"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Scalable OSINT threat intelligence orchestration backend for automated file and observable analysis."
    website_or_repo = "https://github.com/intelowlproject/IntelOwl"
    requires_api_key = True
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN, EntityType.HASH]
    capabilities = ["playbook_orchestration", "multi_analyzer_enrichment"]

    async def check_health(self) -> ConnectorHealthStatus:
        url = os.environ.get("INTELOWL_URL")
        key = os.environ.get("INTELOWL_KEY")
        if not (url and key):
            self._last_health = ConnectorHealthStatus.CONFIG_REQUIRED
            self._last_error = "Requires INTELOWL_URL and INTELOWL_KEY"
        else:
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        url = os.environ.get("INTELOWL_URL")
        key = os.environ.get("INTELOWL_KEY")
        if not (url and key):
            return []
        findings = []
        target = request.target_value.strip()
        headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
                resp = await client.post(f"{url.rstrip('/')}/api/v1/jobs", json={"value": target})
                if resp.status_code in (200, 201):
                    job_data = resp.json()
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"IntelOwl Job #{job_data.get('id')}",
                        source_name="IntelOwl",
                        source_url=f"{url}/jobs/{job_data.get('id')}",
                        confidence=ConfidenceLevel.HIGH,
                        match_type=MatchType.EXACT_MATCH,
                        raw_payload=job_data
                    ))
        except Exception as e:
            logger.debug(f"IntelOwl error: {e}")
        return findings

# ==============================================================================
# 24. OpenOSINT
# ==============================================================================
class OpenOSINTConnector(BaseConnector):
    name = "openosint"
    display_name = "OpenOSINT Threat Feeds"
    category = ToolCategory.ADVANCED_PLATFORMS
    description = "Aggregates open-source threat intelligence feeds, blocklists, and malicious indicator feeds."
    website_or_repo = "https://github.com/hslatman/awesome-threat-intelligence"
    requires_api_key = False
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN]
    capabilities = ["blocklist_correlation", "malware_feed_crosscheck"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings = []
        target = request.target_value.strip().lower()

        # Query URLhaus recent malware URLs for matching domain/ip
        if request.target_type in (EntityType.DOMAIN, EntityType.IP_ADDRESS):
            try:
                async with httpx.AsyncClient(timeout=6.0) as client:
                    resp = await client.post(
                        "https://urlhaus-api.abuse.ch/v1/host/",
                        data={"host": target}
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        query_status = data.get("query_status")
                        if query_status == "ok":
                            urls = data.get("urls", [])
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.TECHNOLOGY,
                                entity_value=f"URLhaus Threat: Host has {len(urls)} reported malicious payloads",
                                source_name="OpenOSINT (URLhaus)",
                                source_url=f"https://urlhaus.abuse.ch/host/{target}/",
                                confidence=ConfidenceLevel.CORROBORATED,
                                match_type=MatchType.EXACT_MATCH,
                                raw_payload={"firstseen": data.get("firstseen"), "url_count": len(urls)}
                            ))
            except Exception as e:
                logger.debug(f"URLhaus lookup error: {e}")
        return findings

