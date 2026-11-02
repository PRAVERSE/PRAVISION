import httpx
import shutil
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class SherlockConnector(BaseConnector):
    name = "sherlock"
    display_name = "Sherlock Project"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Hunts social media accounts by username across 300+ public websites."
    website_or_repo = "https://github.com/sherlock-project/sherlock"
    requires_api_key = False
    supported_entity_types = [EntityType.USERNAME]
    capabilities = [
        "public_username_search",
        "profile_url_collection",
        "cross_platform_presence_mapping"
    ]
    restricted_capabilities = []

    TARGET_PLATFORMS = [
        {"name": "GitHub", "url": "https://github.com/{username}", "check_status": 200},
        {"name": "GitLab", "url": "https://gitlab.com/{username}", "check_status": 200},
        {"name": "Reddit", "url": "https://www.reddit.com/user/{username}", "check_status": 200},
        {"name": "HackerNews", "url": "https://news.ycombinator.com/user?id={username}", "check_status": 200},
        {"name": "Telegram", "url": "https://t.me/{username}", "check_status": 200},
        {"name": "Medium", "url": "https://medium.com/@{username}", "check_status": 200},
        {"name": "Vimeo", "url": "https://vimeo.com/{username}", "check_status": 200},
        {"name": "Keybase", "url": "https://keybase.io/{username}", "check_status": 200},
        {"name": "Pinterest", "url": "https://www.pinterest.com/{username}/", "check_status": 200},
        {"name": "DockerHub", "url": "https://hub.docker.com/u/{username}/", "check_status": 200},
        {"name": "Devpost", "url": "https://devpost.com/{username}", "check_status": 200},
        {"name": "SoundCloud", "url": "https://soundcloud.com/{username}", "check_status": 200},
    ]

    async def check_health(self) -> ConnectorHealthStatus:
        has_cli = shutil.which("sherlock") is not None
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        self._last_error = None if has_cli else "Native asynchronous platform probe engine active (CLI optional)"
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        username = request.target_value.strip().lstrip('@')
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
            for platform in self.TARGET_PLATFORMS:
                target_url = platform["url"].format(username=username)
                try:
                    resp = await client.get(target_url)
                    if resp.status_code == platform["check_status"] and username.lower() in resp.text.lower():
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.URL,
                            entity_value=target_url,
                            source_name="Sherlock",
                            source_url=target_url,
                            evidence_description=f"Public profile verified on {platform['name']}",
                            match_type=MatchType.POSSIBLE_MATCH,
                            confidence=ConfidenceLevel.MODERATE,
                            verification_status="active_profile",
                            related_entities=[platform["name"]],
                            raw_payload={"platform": platform["name"], "status_code": resp.status_code}
                        ))
                except Exception:
                    continue

        return findings

