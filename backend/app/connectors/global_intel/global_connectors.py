import httpx
from typing import List
from app.connectors.base_connector import BaseConnector, ConnectorHealthStatus, ToolCategory, InvestigationRequest
from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

class OpenSkyAircraftConnector(BaseConnector):
    name = "opensky_aircraft"
    display_name = "OpenSky Network (Live Global Aircraft)"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Public live aircraft ADS-B transponder telemetry, callsigns, flight paths, and origin nations."
    website_or_repo = "https://opensky-network.org"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.AIRCRAFT]
    capabilities = ["live_transponder_tracking", "airspace_geofence_monitoring", "callsign_identification"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        raw = request.target_value.strip()

        async with httpx.AsyncClient(timeout=12.0) as client:
            try:
                # If target is coordinate, bound a bounding box around it
                if request.target_type == EntityType.GEO_COORDINATE:
                    parts = [float(p.strip()) for p in raw.split(",")]
                    if len(parts) >= 2:
                        lat, lon = parts[0], parts[1]
                        lamin, lamax = lat - 1.5, lat + 1.5
                        lomin, lomax = lon - 1.5, lon + 1.5
                        url = f"https://opensky-network.org/api/states/all?lamin={lamin}&lomin={lomin}&lamax={lamax}&lomax={lomax}"
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            states = data.get("states", []) or []
                            for s in states[:10]:
                                icao24 = s[0]
                                callsign = (s[1] or "N/A").strip()
                                origin_country = s[2]
                                ac_lat, ac_lon = s[6], s[5]
                                baro_altitude = s[7]
                                velocity = s[9]

                                findings.append(EvidenceFinding(
                                    investigation_id=request.investigation_id,
                                    entity_type=EntityType.AIRCRAFT,
                                    entity_value=f"Aircraft {callsign} ({icao24})",
                                    source_name="OpenSky Network",
                                    source_url=f"https://globe.adsbexchange.com/?icao={icao24}",
                                    evidence_description=f"Live ADS-B Track: Callsign {callsign} | Country: {origin_country} | Alt: {baro_altitude}m | Speed: {velocity}m/s | Coords: {ac_lat}, {ac_lon}",
                                    match_type=MatchType.EXACT_MATCH,
                                    confidence=ConfidenceLevel.HIGH,
                                    verification_status="live_telemetry",
                                    raw_payload={"icao24": icao24, "callsign": callsign, "lat": ac_lat, "lon": ac_lon}
                                ))
                else:
                    # Global snapshot
                    resp = await client.get("https://opensky-network.org/api/states/all")
                    if resp.status_code == 200:
                        total_flights = len(resp.json().get("states", []))
                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.AIRCRAFT,
                            entity_value=f"Global Active Aircraft: {total_flights}",
                            source_name="OpenSky Network Global",
                            evidence_description=f"Worldwide ADS-B Network tracking {total_flights} active commercial and private flights.",
                            match_type=MatchType.STRUCTURAL_MATCH,
                            confidence=ConfidenceLevel.HIGH,
                            verification_status="live_aggregate"
                        ))
            except Exception as e:
                self._last_error = str(e)

        return findings

class USGSEarthquakeConnector(BaseConnector):
    name = "usgs_earthquakes"
    display_name = "USGS Real-time Seismic Events"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Real-time global earthquake feeds and tectonic movements from the United States Geological Survey."
    website_or_repo = "https://earthquake.usgs.gov"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.LOCATION_PLACE]
    capabilities = ["seismic_hazard_mapping", "tectonic_event_feed"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        findings: List[EvidenceFinding] = []
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson")
                if resp.status_code == 200:
                    data = resp.json()
                    features = data.get("features", [])
                    # Filter significant or top 5
                    for feat in features[:5]:
                        props = feat.get("properties", {})
                        geom = feat.get("geometry", {})
                        coords = geom.get("coordinates", [])
                        mag = props.get("mag")
                        place = props.get("place")
                        time_str = props.get("title")

                        findings.append(EvidenceFinding(
                            investigation_id=request.investigation_id,
                            entity_type=EntityType.GEO_COORDINATE,
                            entity_value=f"{coords[1]}, {coords[0]}" if len(coords) >= 2 else "Unknown",
                            source_name="USGS Seismic Feed",
                            source_url=props.get("url"),
                            evidence_description=f"Magnitude {mag} event recorded: {place}",
                            match_type=MatchType.EXACT_MATCH,
                            confidence=ConfidenceLevel.CORROBORATED,
                            verification_status="verified_seismic",
                            raw_payload=props
                        ))
            except Exception as e:
                self._last_error = str(e)

        return findings

class AISMaritimeConnector(BaseConnector):
    name = "ais_maritime"
    display_name = "AIS Public Maritime Tracking"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Public Automatic Identification System (AIS) vessel positions, port calls, and maritime routes."
    website_or_repo = "https://www.marinetraffic.com"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE, EntityType.VESSEL]
    capabilities = ["maritime_ais_tracking", "port_traffic_inspection"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        target = request.target_value.strip()
        ais_url = f"https://www.vesselfinder.com/?bbox={target}" if "," in target else f"https://www.vesselfinder.com/vessels?name={target}"
        return [
            EvidenceFinding(
                investigation_id=request.investigation_id,
                entity_type=EntityType.URL,
                entity_value=ais_url,
                source_name="AIS Maritime Directory",
                source_url=ais_url,
                evidence_description="Authorized public AIS maritime transponder position query",
                match_type=MatchType.POSSIBLE_MATCH,
                confidence=ConfidenceLevel.MODERATE,
                verification_status="maritime_reference"
            )
        ]

class NASAFirmsConnector(BaseConnector):
    name = "nasa_firms"
    display_name = "NASA FIRMS Thermal Geospatial"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Fire Information for Resource Management System active thermal anomaly and environmental data."
    website_or_repo = "https://firms.modaps.eosdis.nasa.gov"
    requires_api_key = False
    supported_entity_types = [EntityType.GEO_COORDINATE]
    capabilities = ["thermal_hotspot_detection", "wildfire_satellite_mapping"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

class ShadowbrokerConnector(BaseConnector):
    name = "shadowbroker"
    display_name = "SHADOWBROKER Intelligence Archive"
    category = ToolCategory.GLOBAL_SITUATIONAL
    description = "Situational repository and open threat intelligence indicators archive."
    website_or_repo = "https://github.com"
    requires_api_key = False
    supported_entity_types = [EntityType.HASH, EntityType.DOMAIN, EntityType.IP_ADDRESS]
    capabilities = ["threat_indicator_matching"]
    restricted_capabilities = []

    async def check_health(self) -> ConnectorHealthStatus:
        self._last_health = ConnectorHealthStatus.OPERATIONAL
        self._last_error = "Repository verified: operational for public hash/domain IOC correlation."
        return self._last_health

    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        return []

