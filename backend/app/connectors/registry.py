import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from app.connectors.base_connector import BaseConnector, ConnectorManifest, ToolCategory
from app.evidence.models import EntityType

# 5.1 Username & Social
from app.connectors.username.ghunt_connector import GHuntConnector
from app.connectors.username.sherlock_connector import SherlockConnector
from app.connectors.username.maigret_connector import MaigretConnector
from app.connectors.username.social_scan_connector import SocialScanConnector
from app.connectors.username.other_username_connectors import (
    MisterHolmesConnector,
    EyeOfGodConnector,
    OsogramConnector,
    InflactConnector,
    StalkScanConnector,
    FacebookSearchConnector
)

# 5.2 Email
from app.connectors.email.email_connectors import (
    HIBPConnector,
    EmailRepConnector,
    EmailHippoConnector,
    HunterConnector,
    ApolloConnector,
    IntelXEmailConnector,
    H8mailConnector
)

# 5.3 Phone
from app.connectors.phone.phone_connectors import (
    PhoneInfogaConnector,
    NumverifyConnector
)

# 5.4 Media & Images
from app.connectors.media.media_connectors import (
    ExifToolConnector,
    FotoForensicsConnector,
    GoogleLensConnector,
    TinEyeConnector,
    YandexImagesConnector,
    LensoConnector,
    SocialCatfishConnector
)

# 5.5 Geographic
from app.connectors.geographic.geo_connectors import (
    SunPositionConnector,
    OpenStreetMapConnector,
    GoogleEarthConnector,
    StreetViewConnector,
    MapillaryConnector
)

# 5.6 Website & Infrastructure
from app.connectors.website.web_infra_connectors import (
    SubfinderConnector,
    DNSxConnector,
    WhatWebConnector,
    GoogleDorkingConnector,
    TheHarvesterConnector,
    PhotonConnector,
    NmapConnector,
    AmassConnector,
    SpiderFootConnector,
    BBOTConnector,
    EholeConnector,
    ReconNgConnector,
    MetagoofilConnector,
    PentestComConnector,
    CertipyConnector,
    GodsEyeReconConnector
)

# 5.7 Global Situational
from app.connectors.global_intel.global_connectors import (
    OpenSkyAircraftConnector,
    USGSEarthquakeConnector,
    AISMaritimeConnector,
    NASAFirmsConnector,
    ShadowbrokerConnector
)

# 5.8 Advanced Platforms
from app.connectors.advanced.advanced_connectors import (
    ShodanConnector,
    CensysConnector,
    IntelXPlatformConnector,
    MaltegoConnector,
    SocialLinksConnector,
    BabelStreetConnector,
    IBMi2Connector,
    OSINTFrameworkConnector
)

# 5.9 Restricted Research
from app.connectors.restricted.restricted_connectors import (
    SeekerConnector,
    RFoneConnector,
    BashHotConnector,
    PimEyesConnector,
    FaceCheckConnector
)

class ConnectorRegistry:
    """Central registry and lifecycle manager for all PRAVISION connectors."""

    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}
        self._register_all()

    def _register_all(self):
        instances: List[BaseConnector] = [
            # Username / Social
            SherlockConnector(),
            MaigretConnector(),
            GHuntConnector(),
            SocialScanConnector(),
            MisterHolmesConnector(),
            EyeOfGodConnector(),
            OsogramConnector(),
            InflactConnector(),
            StalkScanConnector(),
            FacebookSearchConnector(),

            # Email
            HIBPConnector(),
            EmailRepConnector(),
            EmailHippoConnector(),
            HunterConnector(),
            ApolloConnector(),
            IntelXEmailConnector(),
            H8mailConnector(),

            # Phone
            PhoneInfogaConnector(),
            NumverifyConnector(),

            # Media
            ExifToolConnector(),
            FotoForensicsConnector(),
            GoogleLensConnector(),
            TinEyeConnector(),
            YandexImagesConnector(),
            LensoConnector(),
            SocialCatfishConnector(),

            # Geo
            SunPositionConnector(),
            OpenStreetMapConnector(),
            GoogleEarthConnector(),
            StreetViewConnector(),
            MapillaryConnector(),

            # Website & Infra
            SubfinderConnector(),
            DNSxConnector(),
            WhatWebConnector(),
            GoogleDorkingConnector(),
            TheHarvesterConnector(),
            PhotonConnector(),
            NmapConnector(),
            AmassConnector(),
            SpiderFootConnector(),
            BBOTConnector(),
            EholeConnector(),
            ReconNgConnector(),
            MetagoofilConnector(),
            PentestComConnector(),
            CertipyConnector(),
            GodsEyeReconConnector(),

            # Global
            OpenSkyAircraftConnector(),
            USGSEarthquakeConnector(),
            AISMaritimeConnector(),
            NASAFirmsConnector(),
            ShadowbrokerConnector(),

            # Advanced
            ShodanConnector(),
            CensysConnector(),
            IntelXPlatformConnector(),
            MaltegoConnector(),
            SocialLinksConnector(),
            BabelStreetConnector(),
            IBMi2Connector(),
            OSINTFrameworkConnector(),

            # Restricted
            SeekerConnector(),
            RFoneConnector(),
            BashHotConnector(),
            PimEyesConnector(),
            FaceCheckConnector(),
        ]

        for inst in instances:
            self._connectors[inst.name] = inst

    def get_connector(self, name: str) -> Optional[BaseConnector]:
        return self._connectors.get(name)

    def get_all_connectors(self) -> List[BaseConnector]:
        return list(self._connectors.values())

    def get_manifests(self) -> List[ConnectorManifest]:
        return [c.get_manifest() for c in self._connectors.values()]

    def get_connectors_for_entity(self, entity_type: EntityType) -> List[BaseConnector]:
        return [c for c in self._connectors.values() if entity_type in c.supported_entity_types and c.is_enabled]

    async def run_all_health_checks(self):
        tasks = [c.check_health() for c in self._connectors.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        now = datetime.utcnow()
        for c in self._connectors.values():
            c._last_check_time = now

connector_registry = ConnectorRegistry()
