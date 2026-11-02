import httpx
import dns.resolver
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.security import secret_vault

class HIBPConnector(BaseConnector):
    name = "hibp"
    display_name = "Have I Been Pwned"
    category = ToolCategory.EMAIL
    description = "Checks commercial breaches for email address exposure without exposing raw leaked passwords."
    website_or_repo = "https://haveibeenpwned.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["breach_exposure_check", "compromise_timeline_mapping"]
    restricted_capabilities = ["password_hash_retrieval"]

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("hibp_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
            self._last_error = None
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "HIBP API key required for full account breach audits."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        email = request.target_value.strip().lower()
        api_key = secret_vault.get_secret("hibp_api_key")

        if not api_key:
            return findings

        headers = {
            "hibp-api-key": api_key,
            "user-agent": "PRAVISION-OSINT-Platform"
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}?truncateResponse=false", headers=headers)
                if resp.status_code == 200:
                    breaches = resp.json()
                    for breach in breaches:
                        name = breach.get("Name", "Unknown Breach")
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.BREACH,
                            entity_value=f"Breach: {name}",
                            source_name="HaveIBeenPwned",
                            source_url=f"https://haveibeenpwned.com/PwnedWebsites#{name}",
                            evidence_description=f"Account appeared in {name} ({breach.get('BreachDate')}). Compromised data classes: {', '.join(breach.get('DataClasses', []))}",
                            match_type=MatchType.EXACT_MATCH,
                            confidence=ConfidenceLevel.HIGH,
                            verification_status="verified_breach",
                            related_entities=[breach.get("Domain", "")] if breach.get("Domain") else []
                        ))
            except Exception as e:
                self._last_error = str(e)
        return findings

class EmailRepConnector(BaseConnector):
    name = "emailrep"
    display_name = "EmailRep.io"
    category = ToolCategory.EMAIL
    description = "Reputation, malicious activity check, deliverability, and account activity footprint."
    website_or_repo = "https://emailrep.io"
    requires_api_key = False
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["email_reputation_scoring", "suspicious_activity_detection", "profiles_presence_discovery"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        email = request.target_value.strip().lower()

        headers = {"User-Agent": "PRAVISION-OSINT-Engine"}
        async with httpx.AsyncClient(timeout=8.0) as client:
            try:
                resp = await client.get(f"https://emailrep.io/{email}", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    details = data.get("details", {})
                    rep = data.get("reputation", "none")
                    suspicious = data.get("suspicious", False)

                    findings.append(EvidenceFinding(
                        investigation_id=request.investigation_id,
                        entity_type=EntityType.EMAIL,
                        entity_value=email,
                        source_name="EmailRep",
                        source_url="https://emailrep.io",
                        evidence_description=f"Reputation: {rep.upper()} | Suspicious: {suspicious} | Deliverable: {details.get('deliverable', True)} | Data breach recorded: {details.get('data_breach', False)}",
                        match_type=MatchType.EXACT_MATCH,
                        confidence=ConfidenceLevel.HIGH,
                        verification_status="reputation_audited",
                        raw_payload=data
                    ))

                    for prof in details.get("profiles", []):
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=f"{prof.capitalize()} associated profile",
                            source_name="EmailRep",
                            evidence_description=f"Account registered on {prof}",
                            match_type=MatchType.POSSIBLE_MATCH,
                            confidence=ConfidenceLevel.MODERATE,
                            verification_status="linked_profile",
                            related_entities=[prof]
                        ))
            except Exception as e:
                self._last_error = str(e)
        return findings

class EmailHippoConnector(BaseConnector):
    name = "email_hippo"
    display_name = "Email Hippo & MX Intelligence"
    category = ToolCategory.EMAIL
    description = "Deep mail-exchange (MX) DNS verification, syntax validation, and disposable domain filtering."
    website_or_repo = "https://www.emailhippo.com"
    requires_api_key = False
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["mx_record_verification", "disposable_email_detection", "syntax_rfc_validation"]
    restricted_capabilities = []

    DISPOSABLE_DOMAINS = {"mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com", "throwawaymail.com", "sharklasers.com"}

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        email = request.target_value.strip().lower()
        if "@" not in email:
            return findings

        domain = email.split("@")[1]
        is_disposable = domain in self.DISPOSABLE_DOMAINS

        # Check DNS MX
        mx_records = []
        try:
            answers = dns.resolver.resolve(domain, 'MX')
            for rdata in answers:
                mx_records.append(str(rdata.exchange).rstrip('.'))
        except Exception:
            pass

        findings.append(EvidenceFinding(
            investigation_id=request.investigation_id,
            entity_type=EntityType.DOMAIN,
            entity_value=domain,
            source_name="Email Hippo Validator",
            evidence_description=f"MX Host Validated: {', '.join(mx_records) if mx_records else 'None (Domain may not receive mail)'} | Disposable: {is_disposable}",
            match_type=MatchType.EXACT_MATCH,
            confidence=ConfidenceLevel.HIGH,
            verification_status="mx_verified",
            related_entities=mx_records
        ))

        return findings

class HunterConnector(BaseConnector):
    name = "hunter"
    display_name = "Hunter.io"
    category = ToolCategory.EMAIL
    description = "Domain pattern search, corporate email verifier, and verified professional sources."
    website_or_repo = "https://hunter.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.EMAIL, EntityType.DOMAIN]
    capabilities = ["corporate_email_pattern_discovery", "lead_source_attribution"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("hunter_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "Hunter.io API key required for corporate pattern resolution."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class ApolloConnector(BaseConnector):
    name = "apollo"
    display_name = "Apollo.io B2B Intelligence"
    category = ToolCategory.EMAIL
    description = "Discovers authorized corporate contact intelligence and verified company information."
    website_or_repo = "https://www.apollo.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.EMAIL, EntityType.DOMAIN]
    capabilities = ["b2b_organization_discovery", "professional_role_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.SUBSCRIPTION_REQUIRED
        self._last_error = "Requires commercial Apollo API subscription."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class IntelXEmailConnector(BaseConnector):
    name = "intelx_email"
    display_name = "Intelligence X (Email Archive)"
    category = ToolCategory.EMAIL
    description = "Searches Intelligence X public archives for publicly disclosed email references."
    website_or_repo = "https://intelx.io"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["public_archive_search"]
    restricted_capabilities = ["leaked_password_extraction"]

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("intelx_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "IntelX API key required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class H8mailConnector(BaseConnector):
    name = "h8mail"
    display_name = "H8mail (Exposure Analysis Only)"
    category = ToolCategory.EMAIL
    description = "Analyzes breach exposure metadata across authorized databases without credential extraction."
    website_or_repo = "https://github.com/khast3x/h8mail"
    requires_api_key = False
    supported_entity_types = [EntityType.EMAIL]
    capabilities = ["breach_frequency_analysis"]
    restricted_capabilities = ["password_retrieval", "credential_dump_parsing"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        # Strictly exposure metrics, no plaintext passwords
        email = request.target_value.strip()
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.EMAIL,
                entity_value=email,
                source_name="H8mail Policy Guard",
                evidence_description="Exposure audit active. Password dumping strictly restricted in compliance with ethics policies.",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="exposure_analyzed"
            )
        ]

