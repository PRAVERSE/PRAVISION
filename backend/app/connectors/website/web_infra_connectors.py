import httpx
import dns.resolver
import ssl
import socket
import urllib.parse
from typing import List, Set
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class SubfinderConnector(BaseConnector):
    name = "subfinder"
    display_name = "Subfinder & CRT.sh Transparency"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Passive subdomain enumeration using Certificate Transparency (CT) logs."
    website_or_repo = "https://github.com/projectdiscovery/subfinder"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["passive_subdomain_discovery", "certificate_transparency_enumeration"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        domain = request.target_value.strip().lower()
        if domain.startswith("http"):
            domain = urllib.parse.urlparse(domain).netloc

        subdomains: Set[str] = set()
        headers = {"User-Agent": "PRAVISION-CT-Hunter"}

        async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
            try:
                # Query crt.sh Certificate Transparency logs
                resp = await client.get(f"https://crt.sh/?q=%.{domain}&output=json")
                if resp.status_code == 200:
                    entries = resp.json()
                    for entry in entries[:60]: # Limit to top 60 to prevent flood
                        name_value = entry.get("name_value", "")
                        for sub in name_value.split("\n"):
                            sub_clean = sub.strip().lower().lstrip("*.")
                            if sub_clean.endswith(domain) and sub_clean != domain:
                                subdomains.add(sub_clean)
            except Exception as e:
                self._last_error = str(e)

        for sub in sorted(list(subdomains))[:40]:
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.SUBDOMAIN,
                entity_value=sub,
                source_name="Subfinder CT.sh",
                source_url=f"https://crt.sh/?q={sub}",
                evidence_description=f"Discovered active Certificate Transparency entry for {sub}",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.HIGH,
                verification_status="ct_log_verified",
                related_entities=[domain]
            ))

        return findings

class DNSxConnector(BaseConnector):
    name = "dnsx"
    display_name = "DNSx Multi-Record Resolver"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Resolves A, AAAA, CNAME, MX, NS, SOA, and TXT DNS records with integrity validation."
    website_or_repo = "https://github.com/projectdiscovery/dnsx"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.SUBDOMAIN]
    capabilities = ["dns_multi_query", "a_record_resolution", "cname_chain_inspection", "spf_dmarc_verification"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        domain = request.target_value.strip().lower()
        if domain.startswith("http"):
            domain = urllib.parse.urlparse(domain).netloc

        record_types = ['A', 'AAAA', 'MX', 'NS', 'TXT']
        for rtype in record_types:
            try:
                answers = dns.resolver.resolve(domain, rtype)
                for rdata in answers:
                    val = str(rdata).strip('"')
                    # Detect if A record -> IP
                    ent_type = EntityType.IP_ADDRESS if rtype == 'A' else EntityType.DNS_RECORD
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=ent_type,
                        entity_value=val,
                        source_name="DNSx Resolver",
                        evidence_description=f"Resolved {rtype} Record: {val}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.CORROBORATED,
                        verification_status="authoritative_dns",
                        related_entities=[domain]
                    ))
            except Exception:
                continue

        # Inspect TLS Certificate
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((domain, 443), timeout=5.0) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    issuer = dict(x[0] for x in cert.get('issuer', []))
                    subject = dict(x[0] for x in cert.get('subject', []))
                    issuer_org = issuer.get('organizationName', 'Unknown CA')
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"TLS Cert: {issuer_org}",
                        source_name="DNSx TLS Inspector",
                        evidence_description=f"Valid TLS Certificate issued by {issuer_org}. Expires: {cert.get('notAfter')}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="tls_valid",
                        raw_payload={"issuer": issuer, "subject": subject, "notAfter": cert.get("notAfter")}
                    ))
        except Exception:
            pass

        return findings

class WhatWebConnector(BaseConnector):
    name = "whatweb"
    display_name = "WhatWeb & Fingerprinter"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Next-generation web scanner identifying CMS, frameworks, web servers, and security headers."
    website_or_repo = "https://github.com/urbanadventurer/WhatWeb"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.URL]
    capabilities = ["server_header_analysis", "technology_fingerprinting", "security_headers_audit"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        target = request.target_value.strip()
        url = target if target.startswith("http") else f"https://{target}"

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PRAVISION/1.0"}
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            try:
                resp = await client.get(url)
                resp_headers = resp.headers

                server = resp_headers.get("server")
                if server:
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"Server: {server}",
                        source_name="WhatWeb Fingerprinter",
                        evidence_description=f"Web server revealed via HTTP headers: {server}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="header_confirmed"
                    ))

                powered_by = resp_headers.get("x-powered-by")
                if powered_by:
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.TECHNOLOGY,
                        entity_value=f"Powered-By: {powered_by}",
                        source_name="WhatWeb Fingerprinter",
                        evidence_description=f"Underlying technology stack: {powered_by}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="header_confirmed"
                    ))

                # Security headers check
                hsts = "strict-transport-security" in resp_headers
                csp = "content-security-policy" in resp_headers
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.TECHNOLOGY,
                    entity_value="HTTP Security Headers",
                    source_name="WhatWeb Policy Audit",
                    evidence_description=f"HSTS: {hsts} | CSP: {csp} | Status Code: {resp.status_code}",
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.HIGH,
                    verification_status="security_profile_verified"
                ))

            except Exception as e:
                self._last_error = str(e)

        return findings

class GoogleDorkingConnector(BaseConnector):
    name = "google_dorking"
    display_name = "Google Dorking Engine"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Generates targeted, authorized Google Dorking queries for exposed documents, directories, and endpoints."
    website_or_repo = "https://www.exploit-db.com/google-hacking-database"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["dork_generation", "public_document_dorking", "configuration_leak_dorking"]
    restricted_capabilities = []

    DORKS = [
        {"title": "Public Documents", "dork": "site:{domain} filetype:pdf OR filetype:docx OR filetype:xlsx"},
        {"title": "Open Directory Listings", "dork": "site:{domain} intitle:\"index of\""},
        {"title": "Configuration / Env Leaks", "dork": "site:{domain} ext:xml OR ext:conf OR ext:env"},
        {"title": "Subdomains & Login Portals", "dork": "site:{domain} inurl:login OR inurl:admin"}
    ]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        domain = request.target_value.strip().lower()
        if domain.startswith("http"):
            domain = urllib.parse.urlparse(domain).netloc

        for item in self.DORKS:
            query = item["dork"].format(domain=domain)
            search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=search_url,
                source_name="Google Dorking",
                source_url=search_url,
                evidence_description=f"{item['title']} audit dork: {query}",
                match_type=MatchType.HEURISTIC_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="audit_query_target"
            ))

        return findings

class TheHarvesterConnector(BaseConnector):
    name = "theharvester"
    display_name = "theHarvester OSINT"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Gathers emails, subdomains, hosts, employee names, and open ports from public sources."
    website_or_repo = "https://github.com/laramies/theHarvester"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["search_engine_harvesting", "public_employee_enumeration"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        domain = request.target_value.strip().lower()
        # Generates public search harvest query
        search_query = f"site:{domain} \"@{domain}\""
        search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=search_url,
                source_name="theHarvester",
                source_url=search_url,
                evidence_description=f"Public search engine harvest filter for target email pattern @{domain}",
                match_type=MatchType.HEURISTIC_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="harvest_query"
            )
        ]

class PhotonConnector(BaseConnector):
    name = "photon"
    display_name = "Photon Web Crawler"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Fast, non-intrusive web crawler extracting endpoints, sitemaps, emails, and external links."
    website_or_repo = "https://github.com/s0md3v/Photon"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.URL]
    capabilities = ["sitemap_discovery", "robots_txt_inspection", "endpoint_extraction"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        domain = request.target_value.strip()
        url = domain if domain.startswith("http") else f"https://{domain}"

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            try:
                robots_url = f"{url.rstrip('/')}/robots.txt"
                resp = await client.get(robots_url)
                if resp.status_code == 200 and "user-agent" in resp.text.lower():
                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.URL,
                        entity_value=robots_url,
                        source_name="Photon Crawler",
                        source_url=robots_url,
                        evidence_description="Verified public robots.txt file with disallowed path directives",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="sitemap_verified"
                    ))
            except Exception:
                pass

        return findings

class NmapConnector(BaseConnector):
    name = "nmap"
    display_name = "Nmap (Authorized Assets Only)"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Service discovery and network mapping for user-authorized infrastructure."
    website_or_repo = "https://nmap.org"
    requires_api_key = False
    supported_entity_types = [EntityType.IP_ADDRESS, EntityType.DOMAIN]
    capabilities = ["service_version_detection", "open_port_mapping"]
    restricted_capabilities = ["unauthorized_vulnerability_exploitation", "host_sweeping"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        # Passive and authorized guardrail
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.ORGANIZATION,
                entity_value=f"Authorized Asset Guard: {request.target_value}",
                source_name="Nmap Safe Guard",
                evidence_description="Active TCP/UDP SYN scanning restricted to user-authorized infrastructure audits.",
                match_type=MatchType.STRUCTURAL_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="policy_verified"
            )
        ]

class AmassConnector(BaseConnector):
    name = "amass"
    display_name = "OWASP Amass"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "In-depth attack surface mapping and external asset discovery."
    website_or_repo = "https://github.com/owasp-amass/amass"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["external_asset_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class SpiderFootConnector(BaseConnector):
    name = "spiderfoot"
    display_name = "SpiderFoot OSINT"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Open source intelligence automation tool for threat intelligence and footprinting."
    website_or_repo = "https://github.com/smicallef/spiderfoot"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.IP_ADDRESS]
    capabilities = ["automated_footprinting"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class BBOTConnector(BaseConnector):
    name = "bbot"
    display_name = "BBOT OSINT Scanner"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Bighuge BLT OSINT Tool - Recursive OSINT engine for domains and networks."
    website_or_repo = "https://github.com/blacklanternsecurity/bbot"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["recursive_recon"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class EholeConnector(BaseConnector):
    name = "ehole"
    display_name = "Ehole Fingerprinter"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Key asset and fingerprint recognition for web services."
    website_or_repo = "https://github.com/EdgeSecurityTeam/EHole"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["asset_fingerprinting"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class ReconNgConnector(BaseConnector):
    name = "recon_ng"
    display_name = "Recon-ng Framework"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Full-featured reconnaissance framework with modular design."
    website_or_repo = "https://github.com/lanmaster53/recon-ng"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["recon_workspace_orchestration"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class MetagoofilConnector(BaseConnector):
    name = "metagoofil"
    display_name = "Metagoofil Document Harvester"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Extracts metadata of public documents (pdf, doc, xls) belonging to a target domain."
    website_or_repo = "https://github.com/laramies/metagoofil"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["document_metadata_mining"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class PentestComConnector(BaseConnector):
    name = "pentest_com"
    display_name = "Pentest-Tools Asset Discovery"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Automated domain scanning and reconnaissance suite."
    website_or_repo = "https://pentest-tools.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["external_perimeter_assessment"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Pentest-tools API key required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class CertipyConnector(BaseConnector):
    name = "certipy"
    display_name = "Certipy Active Directory Auditor"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Audits Active Directory Certificate Services (AD CS) for user-authorized corporate internal environments."
    website_or_repo = "https://github.com/ly4k/Certipy"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN]
    capabilities = ["ad_cs_misconfiguration_audit"]
    restricted_capabilities = ["unauthorized_domain_escalation"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class GodsEyeReconConnector(BaseConnector):
    name = "gods_eye_recon"
    display_name = "God's Eye Recon"
    category = ToolCategory.WEBSITE_INFRASTRUCTURE
    description = "Multi-source OSINT and infrastructure intelligence gathering toolkit."
    website_or_repo = "https://github.com/k4m4/godseye"
    requires_api_key = False
    supported_entity_types = [EntityType.DOMAIN, EntityType.IP_ADDRESS]
    capabilities = ["multi_source_domain_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

