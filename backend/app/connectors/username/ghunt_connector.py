import os
import asyncio
import re
from pathlib import Path
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class GHuntConnector(BaseConnector):
    name = "ghunt"
    display_name = "GHunt (Spider Edition)"
    category = ToolCategory.USERNAME_SOCIAL
    description = "Inspects Google accounts, Gaia IDs, profile pictures, and associated public services."
    website_or_repo = "https://github.com/mxrch/GHunt"
    requires_api_key = False
    supported_entity_types = [EntityType.EMAIL, EntityType.USERNAME]
    capabilities = [
        "google_account_discovery",
        "gaia_id_extraction",
        "profile_photo_analysis",
        "custom_cover_photo_detection",
        "google_services_footprint"
    ]
    restricted_capabilities = []

    def __init__(self):
        super().__init__()
        self.executable_path = Path(r"C:\Users\hp\.local\bin\ghunt.exe")
        self.creds_path = Path.home() / ".malfrats" / "ghunt" / "creds.m"

    async def check_health(self) -> ConnectorHealthStatus:
        if not self.executable_path.exists():
            self._last_health = ConnectorHealthStatus.UNAVAILABLE
            self._last_error = f"Executable not found at {self.executable_path}"
            return self._last_health

        if not self.creds_path.exists():
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "GHunt session credentials (~/.malfrats/ghunt/creds.m) not found. Run 'ghunt login'."
            return self._last_health

        # Quick version / health test
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            proc = await asyncio.create_subprocess_exec(
                str(self.executable_path), "--help",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode == 0:
                self._last_health = ConnectorHealthStatus.OPERATIONAL
                self._last_error = None
            else:
                self._last_health = ConnectorHealthStatus.PARTIAL
                self._last_error = stderr.decode(errors="replace")[:200]
        except Exception as e:
            self._last_health = ConnectorHealthStatus.UNAVAILABLE
            self._last_error = str(e)

        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        target = request.target_value.strip()

        # If it's a username, check if target has @gmail.com or append if needed
        email_target = target if "@" in target else f"{target}@gmail.com"

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.executable_path), "email", email_target,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=35)
            output = stdout_bytes.decode("utf-8", errors="replace")

            # Parse Gaia ID
            gaia_match = re.search(r"Gaia ID\s*:\s*(\d+)", output)
            if gaia_match:
                gaia_id = gaia_match.group(1)
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.ORGANIZATION,
                    entity_value=f"Google Account (Gaia: {gaia_id})",
                    source_name="GHunt",
                    source_url=f"https://contacts.google.com/person/{gaia_id}",
                    evidence_description=f"Verified public Google Account with Gaia ID: {gaia_id}",
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.HIGH,
                    verification_status="verified_google_identity",
                    raw_payload={"gaia_id": gaia_id, "email": email_target}
                ))

            # Parse Profile Photo
            photo_match = re.search(r"Custom profile picture.*?\n\s*=>\s*(https?://\S+)", output)
            if photo_match:
                photo_url = photo_match.group(1)
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.IMAGE,
                    entity_value=photo_url,
                    source_name="GHunt",
                    source_url=photo_url,
                    evidence_description="Discovered custom Google Account profile picture",
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.HIGH,
                    verification_status="verified_asset"
                ))

            # Parse Cover Photo
            cover_match = re.search(r"Custom cover picture.*?\n\s*=>\s*(https?://\S+)", output)
            if cover_match:
                cover_url = cover_match.group(1)
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.IMAGE,
                    entity_value=cover_url,
                    source_name="GHunt",
                    source_url=cover_url,
                    evidence_description="Discovered custom Google Account banner/cover picture",
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.HIGH,
                    verification_status="verified_asset"
                ))

            # Parse services (Maps, Calendar, YouTube, etc.)
            if "Google Maps" in output:
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.TECHNOLOGY,
                    entity_value="Google Maps Contributions",
                    source_name="GHunt",
                    evidence_description="Public reviews/photos contributed on Google Maps",
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.MODERATE
                ))

        except Exception as e:
            self._last_error = str(e)

        return findings
