import asyncio
import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.evidence.models import EvidenceFinding, EntityType

logger = logging.getLogger("pravision.connectors")

class ConnectorHealthStatus(str, Enum):
    OPERATIONAL = "operational"
    PARTIAL = "partial"
    CONFIG_REQUIRED = "config_required"
    AUTH_REQUIRED = "auth_required"
    SUBSCRIPTION_REQUIRED = "subscription_required"
    UNAVAILABLE = "unavailable"
    RESTRICTED = "restricted"

class ToolCategory(str, Enum):
    USERNAME_SOCIAL = "username_social"
    EMAIL = "email"
    PHONE = "phone"
    MEDIA_IMAGE = "media_image"
    GEOGRAPHIC = "geographic"
    WEBSITE_INFRASTRUCTURE = "website_infrastructure"
    GLOBAL_SITUATIONAL = "global_situational"
    ADVANCED_PLATFORMS = "advanced_platforms"
    RESTRICTED_RESEARCH = "restricted_security_research"

class ConnectorManifest(BaseModel):
    name: str
    display_name: str
    category: ToolCategory
    description: str
    website_or_repo: str
    installed: bool
    configured: bool
    authenticated: Optional[bool] = None
    health: ConnectorHealthStatus
    capabilities: List[str]
    enabled_capabilities: List[str]
    restricted_capabilities: List[str] = Field(default_factory=list)
    requires_api_key: bool = False
    is_commercial: bool = False
    last_health_check: Optional[datetime] = None
    last_error: Optional[str] = None
    supported_entity_types: List[EntityType] = Field(default_factory=list)

class InvestigationRequest(BaseModel):
    investigation_id: str
    target_value: str
    target_type: EntityType
    mode: str
    depth: int = 1
    parameters: Dict[str, Any] = Field(default_factory=dict)

class BaseConnector(ABC):
    """
    Standard abstract contract for all PRAVISION connectors.
    Guarantees isolation, rich telemetry, robust exception handling, and provenance tracking.
    """
    name: str = "base"
    display_name: str = "Base Connector"
    category: ToolCategory = ToolCategory.USERNAME_SOCIAL
    description: str = ""
    website_or_repo: str = ""
    requires_api_key: bool = False
    is_commercial: bool = False
    supported_entity_types: List[EntityType] = []
    capabilities: List[str] = []
    restricted_capabilities: List[str] = []

    def __init__(self):
        self._is_enabled: bool = True
        self._last_health: ConnectorHealthStatus = ConnectorHealthStatus.CONFIG_REQUIRED
        self._last_error: Optional[str] = None
        self._last_check_time: Optional[datetime] = None
        self._lock = asyncio.Lock()

    @property
    def is_enabled(self) -> bool:
        return self._is_enabled

    def set_enabled(self, enabled: bool):
        self._is_enabled = enabled

    @abstractmethod
    async def check_health(self) -> ConnectorHealthStatus:
        """Runs non-destructive verification of executables, dependencies, and connectivity."""
        raise NotImplementedError

    @abstractmethod
    async def execute(self, request: InvestigationRequest) -> List[EvidenceFinding]:
        """Runs the investigation action and returns structured EvidenceFinding items."""
        raise NotImplementedError

    async def safe_execute(self, request: InvestigationRequest, timeout_seconds: int = 35) -> List[EvidenceFinding]:
        """Wrapper ensuring timeouts, failure containment, and cancellation."""
        if not self._is_enabled:
            logger.info(f"Connector {self.name} is disabled. Skipping.")
            return []

        if request.target_type not in self.supported_entity_types:
            logger.debug(f"Connector {self.name} does not support {request.target_type}. Skipping.")
            return []

        try:
            return await asyncio.wait_for(self.execute(request), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"Connector {self.name} timed out after {timeout_seconds}s on investigation {request.investigation_id}.")
            return []
        except Exception as e:
            logger.error(f"Connector {self.name} encountered an error: {e}")
            self._last_error = str(e)
            return []

    def get_manifest(self) -> ConnectorManifest:
        return ConnectorManifest(
            name=self.name,
            display_name=self.display_name,
            category=self.category,
            description=self.description,
            website_or_repo=self.website_or_repo,
            installed=self._last_health != ConnectorHealthStatus.UNAVAILABLE,
            configured=self._last_health not in (ConnectorHealthStatus.CONFIG_REQUIRED, ConnectorHealthStatus.AUTH_REQUIRED),
            authenticated=True if self._last_health == ConnectorHealthStatus.OPERATIONAL and self.requires_api_key else (False if self.requires_api_key else None),
            health=self._last_health,
            capabilities=self.capabilities,
            enabled_capabilities=[c for c in self.capabilities if c not in self.restricted_capabilities],
            restricted_capabilities=self.restricted_capabilities,
            requires_api_key=self.requires_api_key,
            is_commercial=self.is_commercial,
            last_health_check=self._last_check_time,
            last_error=self._last_error,
            supported_entity_types=self.supported_entity_types
        )
