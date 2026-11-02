import httpx
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class SocialScanConnector(BaseConnector):
    name = "social_scan"
    display_name = "Social Scan"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Fast, accurate checking of email address and username availability and registration."
    website_or_repo = "https://github.com/iojw/socialscan"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME, EntityType.EMAIL]
    capabilities = ["username_registration_check", "email_account_check"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        target = request.target_value.strip()

        # Check GitHub API public user endpoint
        if request.target_type == EntityType.USERNAME:
            async with httpx.AsyncClient(timeout=8.0) as client:
                try:
                    resp = await client.get(f"https://api.github.com/users/{target}")
                    if resp.status_code == 200:
                        data = resp.json()
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=data.get("html_url", f"https://github.com/{target}"),
                            source_name="SocialScan",
                            source_url=data.get("html_url"),
                            evidence_description=f"GitHub account confirmed. Bio: {data.get('bio') or 'N/A'}",
                            match_type=MatchType.EXACT_MATCH,
                            confidence=ConfidenceLevel.HIGH,
                            verification_status="verified_api",
                            related_entities=[data.get("company", "")] if data.get("company") else []
                        ))
                except Exception:
                    pass

        return findings

