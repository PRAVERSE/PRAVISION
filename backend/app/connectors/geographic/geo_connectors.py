import httpx
from datetime import datetime
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel
from app.geo.solar_calculator import solar_calculator

class SunPositionConnector(BaseConnector):
    name = "sun_position"
    display_name = "SunCalc & Shadow Direction Engine"
    category = ToolCategory.GEOGRAPHIC
    description = "Calculates exact solar elevation angle, azimuth, and cast-shadow length ratio for coordinates."
    website_or_repo = "https://suncalc.org"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = ["solar_altitude_calculation", "solar_azimuth_calculation", "shadow_vector_forensics"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        raw = request.target_value.strip()

        try:
            parts = [float(p.strip()) for p in raw.split(",")]
            if len(parts) >= 2:
                lat, lon = parts[0], parts[1]
                solar = solar_calculator.calculate(lat, lon, datetime.utcnow())

                findings.append(EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.GEO_COORDINATE,
                    entity_value=f"Solar Analysis: {lat}, {lon}",
                    source_name="SunCalc Ephemeris",
                    evidence_description=(
                        f"Sun elevation: {solar['solar_elevation_deg']}° | "
                        f"Sun azimuth: {solar['solar_azimuth_deg']}° | "
                        f"Shadow direction: {solar['shadow_direction_deg']}° | "
                        f"Shadow ratio: {solar['shadow_length_multiplier']}x object height | "
                        f"Daylight: {solar['is_daylight']}"
                    ),
                    match_type=MatchType.EXACT_MATCH,
                    confidence=ConfidenceLevel.CORROBORATED,
                    verification_status="mathematical_verification",
                    raw_payload=solar
                ))
        except Exception as e:
            self._last_error = str(e)

        return findings

class OpenStreetMapConnector(BaseConnector):
    name = "openstreetmap"
    display_name = "OpenStreetMap & Nominatim"
    category = ToolCategory.GEOGRAPHIC
    description = "Open geographic data, reverse geocoding, boundary analysis, and open landmarks."
    website_or_repo = "https://www.openstreetmap.org"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.LOCATION_PLACE]
    capabilities = ["reverse_geocoding", "open_landmark_discovery", "administrative_boundary_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        raw = request.target_value.strip()

        headers = {"User-Agent": "PRAVISION-OSINT-Platform (nominatim-lookup)"}
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                if request.target_type == EntityType.GEO_COORDINATE:
                    parts = [p.strip() for p in raw.split(",")]
                    if len(parts) >= 2:
                        lat, lon = parts[0], parts[1]
                        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            display_name = data.get("display_name", "OpenStreetMap Resolved Location")
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.LOCATION_PLACE,
                                entity_value=display_name,
                                source_name="OpenStreetMap Nominatim",
                                source_url=f"https://www.openstreetmap.org/#map=17/{lat}/{lon}",
                                evidence_description=f"Reverse geocoded location: {display_name}",
                                match_type=MatchType.EXACT_MATCH,
                                confidence=ConfidenceLevel.HIGH,
                                verification_status="osm_verified",
                                raw_payload=data
                            ))
                else:
                    # Forward geocoding query
                    url = f"https://nominatim.openstreetmap.org/search?format=jsonv2&q={urllib.parse.quote_plus(raw)}"
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        results = resp.json()
                        if results:
                            top = results[0]
                            findings.append(EvidenceFinding(
                                investigation_id=request.investigation_id,
                                entity_type=EntityType.GEO_COORDINATE,
                                entity_value=f"{top.get('lat')}, {top.get('lon')}",
                                source_name="OpenStreetMap Search",
                                source_url=f"https://www.openstreetmap.org/#map=16/{top.get('lat')}/{top.get('lon')}",
                                evidence_description=f"Geocoded coordinate: {top.get('display_name')}",
                                match_type=MatchType.EXACT_MATCH,
                                confidence=ConfidenceLevel.HIGH,
                                verification_status="geocoded",
                                raw_payload=top
                            ))
            except Exception as e:
                self._last_error = str(e)

        return findings

class GoogleEarthConnector(BaseConnector):
    name = "google_earth"
    display_name = "Google Earth 3D"
    category = ToolCategory.GEOGRAPHIC
    description = "Satellite imagery, historical satellite basemaps, and terrain visualization."
    website_or_repo = "https://earth.google.com"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.LOCATION_PLACE]
    capabilities = ["satellite_imagery_query", "3d_terrain_reference"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        earth_url = f"https://earth.google.com/web/search/{urllib.parse.quote_plus(target)}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=earth_url,
                source_name="Google Earth",
                source_url=earth_url,
                evidence_description="Satellite 3D terrain and structural imagery reference",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="satellite_reference"
            )
        ]

class StreetViewConnector(BaseConnector):
    name = "streetview"
    display_name = "Google Street View"
    category = ToolCategory.GEOGRAPHIC
    description = "Street-level panoramic street view exploration for landmark validation."
    website_or_repo = "https://www.google.com/maps"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = ["street_level_panorama_reference"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        sv_url = f"https://www.google.com/maps/@?api=1&map_action=pano&viewpoint={target}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=sv_url,
                source_name="Street View",
                source_url=sv_url,
                evidence_description="Street-level visual ground truth panoramic reference",
                match_type=MatchType.EXACT_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="streetview_reference"
            )
        ]

class MapillaryConnector(BaseConnector):
    name = "mapillary"
    display_name = "Mapillary Crowdsourced Street Imagery"
    category = ToolCategory.GEOGRAPHIC
    description = "Global crowdsourced street-level photography with open geometric point cloud data."
    website_or_repo = "https://www.mapillary.com"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = ["open_street_imagery_discovery"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        parts = [p.strip() for p in request.target_value.split(",")]
        if len(parts) >= 2:
            lat, lon = parts[0], parts[1]
            map_url = f"https://www.mapillary.com/app/?lat={lat}&lng={lon}&z=17"
            return [
                EvidenceFinding(
                    investigation_id=request.investigation_id,
                    entity_type=EntityType.URL,
                    entity_value=map_url,
                    source_name="Mapillary",
                    source_url=map_url,
                    evidence_description="Crowdsourced street-level geotagged image sequence link",
                    match_type=MatchType.POSSIBLE_MATCH,
                    confidence=ConfidenceLevel.LOW,
                    verification_status="open_imagery_link"
                )
            ]
        return []
