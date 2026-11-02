from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class ConfidenceLevel(str, Enum):
    UNVERIFIED = "unverified"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CORROBORATED = "independently_corroborated"

class MatchType(str, Enum):
    EXACT_MATCH = "exact_match"
    POSSIBLE_MATCH = "possible_match"
    HEURISTIC_MATCH = "heuristic_match"
    STRUCTURAL_MATCH = "structural_match"
    CONTRADICTORY = "contradictory"
    OUTDATED = "outdated"

class EntityType(str, Enum):
    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    URL = "url"
    PERSON_NAME = "person_name"
    ORGANIZATION = "organization"
    IMAGE = "image"
    DOCUMENT = "document"
    GEO_COORDINATE = "geo_coordinate"
    LOCATION_PLACE = "location_place"
    HASH = "hash"
    AIRCRAFT = "aircraft"
    VESSEL = "vessel"
    TECHNOLOGY = "technology"
    DNS_RECORD = "dns_record"
    BREACH = "breach_record"

class EvidenceFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    investigation_id: str
    entity_type: EntityType
    entity_value: str
    source_name: str
    source_url: Optional[str] = None
    collection_timestamp: datetime = Field(default_factory=datetime.utcnow)
    evidence_description: str = Field(default="")
    match_type: MatchType = MatchType.POSSIBLE_MATCH
    confidence: ConfidenceLevel = ConfidenceLevel.UNVERIFIED
    verification_status: str = "unverified"
    limitations: Optional[str] = None
    related_entities: List[str] = Field(default_factory=list)
    supporting_sources: List[str] = Field(default_factory=list)
    raw_payload: Dict[str, Any] = Field(default_factory=dict)

class GraphNode(BaseModel):
    id: str
    label: str
    type: EntityType
    confidence: ConfidenceLevel
    properties: Dict[str, Any] = Field(default_factory=dict)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    sources: List[str] = Field(default_factory=list)

class GraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str
    target: str
    relation: str
    confidence: ConfidenceLevel
    evidence_id: Optional[str] = None
    source_name: str
    properties: Dict[str, Any] = Field(default_factory=dict)

class IntelligenceGraph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

