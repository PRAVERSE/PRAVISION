import re
import phonenumbers
from phonenumbers import geocoder, carrier, timezone
import urllib.parse
from typing import List, Optional
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.security import secret_vault

LINE_TYPE_MAP = {
    phonenumbers.PhoneNumberType.FIXED_LINE: "Fixed Line",
    phonenumbers.PhoneNumberType.MOBILE: "Mobile",
    phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed Line or Mobile",
    phonenumbers.PhoneNumberType.TOLL_FREE: "Toll Free",
    phonenumbers.PhoneNumberType.PREMIUM_RATE: "Premium Rate",
    phonenumbers.PhoneNumberType.SHARED_COST: "Shared Cost",
    phonenumbers.PhoneNumberType.VOIP: "VoIP (Virtual Number)",
    phonenumbers.PhoneNumberType.PERSONAL_NUMBER: "Personal Number",
    phonenumbers.PhoneNumberType.PAGER: "Pager",
    phonenumbers.PhoneNumberType.UAN: "Universal Access Number (UAN)",
    phonenumbers.PhoneNumberType.VOICEMAIL: "Voicemail",
    phonenumbers.PhoneNumberType.UNKNOWN: "Unknown Line Type",
}

def parse_phone_resiliently(raw_input: str) -> Optional[phonenumbers.PhoneNumber]:
    """
    Parses a phone number input with deterministic international resolution:
    - Supports international format with leading + (e.g. +91 9820012345, +1 415 555 2671)
    - Supports prefixes 00 or 011
    - Supports Indian mobile numbers with/without +91, domestic trunk 0, or direct 10-digit series (6, 7, 8, 9)
    - Disambiguates 10-digit numbers between ITU-T national numbering plans
    - Rejects invalid or unallocated strings safely without silent misattribution
    """
    cleaned = raw_input.strip()
    digits_only = re.sub(r'[^\d]', '', cleaned)
    if not digits_only or len(digits_only) < 7:
        return None

    # 1. Leading +
    if cleaned.startswith("+"):
        try:
            p = phonenumbers.parse(cleaned, None)
            if phonenumbers.is_valid_number(p) or phonenumbers.is_possible_number(p):
                return p
        except Exception:
            pass

    # 2. International prefixes 00 or 011
    if digits_only.startswith("00") and len(digits_only) > 8:
        try:
            p = phonenumbers.parse("+" + digits_only[2:], None)
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass
    elif digits_only.startswith("011") and len(digits_only) > 9:
        try:
            p = phonenumbers.parse("+" + digits_only[3:], None)
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass

    # 3. Explicit India prefix without + (12 digits starting with 91)
    if len(digits_only) == 12 and digits_only.startswith("91"):
        try:
            p = phonenumbers.parse("+" + digits_only, None)
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass

    # 4. Indian domestic trunk: 0 followed by 10 digits
    if len(digits_only) == 11 and digits_only.startswith("0"):
        try:
            p = phonenumbers.parse(digits_only[1:], "IN")
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass

    # 5. North American 11 digits: 1 followed by 10 digits
    if len(digits_only) == 11 and digits_only.startswith("1"):
        try:
            p = phonenumbers.parse("+" + digits_only, None)
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass

    # 6. 10-digit evaluation (disambiguate IN vs US vs others)
    if len(digits_only) == 10:
        p_in = None
        p_us = None
        try:
            p_in = phonenumbers.parse(digits_only, "IN")
        except Exception:
            pass
        try:
            p_us = phonenumbers.parse(digits_only, "US")
        except Exception:
            pass

        in_valid = p_in and phonenumbers.is_valid_number(p_in)
        us_valid = p_us and phonenumbers.is_valid_number(p_us)

        if in_valid and not us_valid:
            return p_in
        elif us_valid and not in_valid:
            return p_us
        elif in_valid and us_valid:
            # If formatted with US style (e.g. '(415)' or '-') or begins with non-Indian mobile range
            if "(" in cleaned or "-" in cleaned or digits_only[0] not in "6789":
                return p_us
            else:
                return p_in

    # 7. Fallback regional scan for valid numbers
    for reg in ["IN", "US", "GB", "CA", "AU", "DE", "FR"]:
        try:
            p = phonenumbers.parse(cleaned, reg)
            if phonenumbers.is_valid_number(p):
                return p
        except Exception:
            pass

    # 8. No silent guessing of invalid strings
    return None

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
            parsed = parse_phone_resiliently(raw_number)
            if not parsed:
                return findings

            is_valid = phonenumbers.is_valid_number(parsed)
            formatted_e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            formatted_intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
            formatted_nat = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            formatted_rfc3966 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.RFC3966)

            geo_loc = geocoder.description_for_number(parsed, "en") or "Global / International Allocation"
            car_name = carrier.name_for_number(parsed, "en") or "Network / Unassigned Carrier"
            num_type_code = phonenumbers.number_type(parsed)
            line_type = LINE_TYPE_MAP.get(num_type_code, "Standard Telecom Line")
            timezones = list(timezone.time_zones_for_number(parsed))

            findings.append(EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.PHONE,
                entity_value=formatted_e164,
                source_name="PhoneInfoga Engine",
                evidence_description=f"Valid: {is_valid} | Line Type: {line_type} | Intl: {formatted_intl} | Nat: {formatted_nat} | Region: {geo_loc} | Carrier: {car_name} | Timezones: {', '.join(timezones)}",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.HIGH if is_valid else ConfidenceLevel.MODERATE,
                verification_status="e164_verified",
                raw_payload={
                    "e164": formatted_e164,
                    "international": formatted_intl,
                    "national": formatted_nat,
                    "rfc3966": formatted_rfc3966,
                    "valid": is_valid,
                    "line_type": line_type,
                    "region": geo_loc,
                    "carrier": car_name,
                    "timezones": timezones
                }
            ))

            # Add Location Entity
            if geo_loc and geo_loc != "Global / International Allocation":
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

