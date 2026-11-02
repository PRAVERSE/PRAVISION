import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Index
)
from sqlalchemy.orm import relationship

from app.storage.database import Base

def gen_uuid() -> str:
    return str(uuid.uuid4())

class CaseModel(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    case_number = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(128), default="Analyst")
    status = Column(String(32), default="active", index=True)  # active, closed, archived, suspended
    classification = Column(String(32), default="UNCLASSIFIED")  # UNCLASSIFIED, RESTRICTED, CONFIDENTIAL, SECRET
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    investigations = relationship("InvestigationModel", back_populates="case", cascade="all, delete-orphan")
    entities = relationship("EntityModel", back_populates="case", cascade="all, delete-orphan")
    evidences = relationship("EvidenceModel", back_populates="case", cascade="all, delete-orphan")

class InvestigationModel(Base):
    __tablename__ = "investigations"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True, index=True)
    root_input = Column(String(512), nullable=False)
    root_type = Column(String(64), nullable=False)
    mode = Column(String(64), nullable=False)
    max_depth = Column(Integer, default=2)
    status = Column(String(32), default="initialized", index=True)  # initialized, running, completed, cancelled, error
    total_findings = Column(Integer, default=0)
    verified_relationships = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    case = relationship("CaseModel", back_populates="investigations")
    entities = relationship("EntityModel", back_populates="investigation", cascade="all, delete-orphan")
    relationships = relationship("RelationshipModel", back_populates="investigation", cascade="all, delete-orphan")
    evidences = relationship("EvidenceModel", back_populates="investigation", cascade="all, delete-orphan")

class EntityModel(Base):
    __tablename__ = "entities"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_value = Column(String(1024), nullable=False)
    normalized_value = Column(String(1024), nullable=False, index=True)
    confidence = Column(String(32), default="moderate")
    match_type = Column(String(32), default="possible_match")
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    properties = Column(JSON, default=dict)

    # Relationships
    case = relationship("CaseModel", back_populates="entities")
    investigation = relationship("InvestigationModel", back_populates="entities")

class RelationshipModel(Base):
    __tablename__ = "relationships"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False)
    confidence = Column(String(32), default="moderate")
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("InvestigationModel", back_populates="relationships")

class EvidenceModel(Base):
    __tablename__ = "evidences"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_id = Column(String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    connector_name = Column(String(128), nullable=False)
    source_url = Column(String(2048), nullable=True)
    raw_data = Column(JSON, default=dict)
    
    # Immutable Storage & Vault tracking
    b2_file_key = Column(String(512), nullable=True, index=True)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256
    file_mime_type = Column(String(128), nullable=True)
    file_size = Column(Integer, default=0)
    storage_backend = Column(String(32), default="local")  # b2_cloud, local_vault, memory
    collected_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship("CaseModel", back_populates="evidences")
    investigation = relationship("InvestigationModel", back_populates="evidences")

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user = Column(String(128), default="Analyst")
    action = Column(String(64), nullable=False, index=True)  # create_case, export_report, query_target, delete_case
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(128), nullable=True)
    ip_address = Column(String(64), default="127.0.0.1")
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
