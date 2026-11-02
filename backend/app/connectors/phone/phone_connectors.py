import phonenumbers
from phonenumbers import geocoder, carrier, timezone
import urllib.parse
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.security import secret_vault

class PhoneInfogaConnector(BaseConnector):
    name = "phoneinfoga"
    display_name = "PhoneInfoga & E.164 Parser"
    category = ToolCategory.PHONE
    description = "Advanced phone number information gathering, international parsing, carrier detection, and footprint generation."
    website_or_repo = "https://github.com/sundowndev/phoneinfoga"
    requires_api_key = False
    supported_entity_types = [EntityType.PHONE]
    capabilities = [
        "international_number_parsing",
        "e164_normalization",
        "carrier_classification",
        "geographic_origin_resolution",
        "public_directory_footprint_generation"
    ]
    restricted_capabilities = ["subscriber_identity_tracking", "realtime_cell_tower_triangulation"]

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        raw_number = request.target_value.strip()

        try:
            # Parse using phonenumbers
            parsed = phonenumbers.parse(raw_number, None)
            if not phonenumbers.is_possible_number(parsed):
                return findings

            is_valid = phonenumbers.is_valid_number(parsed)
            formatted_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            formatted_intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            formatted_nat = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)

            geo_loc = geocoder.description_for_number(parsed, "en") or "Global/International"
            car_name = carrier.name_for_number(parsed, "en") or "Unspecified Carrier"
            timezones = list(timezone.time_zones_for_number(parsed))

            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.PHONE,
                entity_value=formatted_e164,
                source_name="PhoneInfoga Engine",
                evidence_description=f"Valid: {is_valid} | Intl: {formatted_intl} | Nat: {formatted_nat} | Region: {geo_loc} | Carrier: {car_name} | Timezones: {', '.join(timezones)}",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.HIGH,
                verification_status="e164_verified",
                raw_payload={
                    "e164": formatted_e164,
                    "valid": is_valid,
                    "region": geo_loc,
                    "carrier": car_name,
                    "timezones": timezones
                }
            ))

            # Add Location Entity
            if geo_loc and geo_loc != "Global/International":
                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.LOCATION_PLACE,
                    entity_value=geo_loc,
                    source_name="PhoneInfoga Geocoder",
                    evidence_description=f"Telecommunications region allocated to {geo_loc}",
                    match_type=MatchType.STRUCTURAL_MATCH,
                    confidence=ConfidenceLevel.MODERATE,
                    verification_status="telecom_region"
                ))

            # Generate public directory research query
            dork_query = f'"{formatted_intl}" OR "{formatted_e164}" OR "{formatted_nat}"'
            search_url = f"https://www.google.com/search?q={urllib.parse.quote_plus(dork_query)}"
            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=search_url,
                source_name="PhoneInfoga Footprint",
                source_url=search_url,
                evidence_description="Public search query across indexed corporate directories and listings",
                match_type=MatchType.HEURISTIC_MATCH,
                confidence=ConfidenceLevel.LOW,
                verification_status="search_query"
            ))

        except Exception as e:
            self._last_error = str(e)

        return findings

class NumverifyConnector(BaseConnector):
    name = "numverify"
    display_name = "Numverify API"
    category = ToolCategory.PHONE
    description = "Global phone number validation, line-type intelligence, and carrier lookup."
    website_or_repo = "https://numverify.com"
    requires_api_key = True
    is_commercial = True
    supported_entity_types = [EntityType.PHONE]
    capabilities = ["carrier_detection", "line_type_intelligence"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        if secret_vault.has_secret("numverify_api_key"):
            self._last_health = ConnectorHealthStatus.OPERATIONAL
        else:
            self._last_health = ConnectorHealthStatus.AUTH_REQUIRED
            self._last_error = "Numverify API key required."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

