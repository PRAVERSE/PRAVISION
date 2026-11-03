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

class UserModel(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(32), default="analyst", nullable=False, index=True)  # admin, case_officer, analyst
    full_name = Column(String(128), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Relationships
    owned_cases = relationship("CaseModel", back_populates="owner")
    case_memberships = relationship("CaseMembershipModel", back_populates="user", cascade="all, delete-orphan")

class CaseMembershipModel(Base):
    __tablename__ = "case_memberships"
    __table_args__ = (
        Index("ix_case_memberships_case_user", "case_id", "user_id", unique=True),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(32), default="read", nullable=False)  # owner, editor, viewer
    granted_at = Column(DateTime, default=datetime.utcnow)
    granted_by = Column(String(36), nullable=True)

    # Relationships
    case = relationship("CaseModel", back_populates="memberships")
    user = relationship("UserModel", back_populates="case_memberships")

class RevokedTokenModel(Base):
    __tablename__ = "revoked_tokens"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    token_jti = Column(String(64), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False, index=True)

class CaseModel(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    case_number = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_by = Column(String(128), default="Analyst")
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(32), default="active", index=True)  # active, closed, archived, suspended
    classification = Column(String(32), default="UNCLASSIFIED")  # UNCLASSIFIED, RESTRICTED, CONFIDENTIAL, SECRET
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("UserModel", back_populates="owned_cases")
    memberships = relationship("CaseMembershipModel", back_populates="case", cascade="all, delete-orphan")
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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    case = relationship("CaseModel", back_populates="investigations")
    entities = relationship("EntityModel", back_populates="investigation", cascade="all, delete-orphan")
    relationships = relationship("RelationshipModel", back_populates="investigation", cascade="all, delete-orphan")
    evidences = relationship("EvidenceModel", back_populates="investigation", cascade="all, delete-orphan")

class EntityModel(Base):
    __tablename__ = "entities"
    __table_args__ = (
        Index("ix_entities_case_type", "case_id", "entity_type"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=True, index=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=True, index=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_value = Column(String(1024), nullable=False)
    normalized_value = Column(String(1024), nullable=False, index=True)
    confidence = Column(String(32), default="moderate")
    match_type = Column(String(32), default="possible_match")
    verification_status = Column(String(32), default="unverified", index=True)  # unverified, analyst_verified, corroborated, disputed
    aliases = Column(JSON, default=list)
    identifiers = Column(JSON, default=dict)
    sources = Column(JSON, default=list)
    merged_into_id = Column(String(36), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True, index=True)
    merge_history = Column(JSON, default=list)
    change_history = Column(JSON, default=list)
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    properties = Column(JSON, default=dict)

    # Relationships
    case = relationship("CaseModel", back_populates="entities")
    investigation = relationship("InvestigationModel", back_populates="entities")
    merged_into = relationship("EntityModel", remote_side=[id], backref="merged_entities", foreign_keys=[merged_into_id])
    merge_logs = relationship("EntityMergeLogModel", back_populates="canonical_entity", cascade="all, delete-orphan", passive_deletes=True)

class RelationshipModel(Base):
    __tablename__ = "relationships"
    __mapper_args__ = {"confirm_deleted_rows": False}
    __table_args__ = (
        Index("ix_relationships_src_tgt", "source_id", "target_id"),
        Index("ix_relationships_inv_type", "investigation_id", "relationship_type"),
    )

    id = Column(String(36), primary_key=True, default=gen_uuid)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type = Column(String(64), nullable=False)
    confidence = Column(String(32), default="moderate")
    creation_method = Column(String(64), default="direct_observation", index=True)  # direct_observation, source_reported, analyst_created, inferred_candidate
    source_ref = Column(String(2048), nullable=True)
    observation_timestamp = Column(DateTime, default=datetime.utcnow)
    verification_status = Column(String(32), default="unverified", index=True)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    investigation = relationship("InvestigationModel", back_populates="relationships")

class EvidenceModel(Base):
    __tablename__ = "evidences"
    __table_args__ = (
        Index("ix_evidences_case_backend", "case_id", "storage_backend"),
    )

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
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    case = relationship("CaseModel", back_populates="evidences")
    investigation = relationship("InvestigationModel", back_populates="evidences")

class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user = Column(String(128), default="Analyst")
    actor_id = Column(String(36), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)  # create_case, export_report, query_target, delete_case
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(128), nullable=True, index=True)
    outcome = Column(String(32), default="success", index=True)  # success, failure, denied
    ip_address = Column(String(64), default="127.0.0.1")
    details = Column(JSON, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class EntityMergeLogModel(Base):
    __tablename__ = "entity_merge_logs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    canonical_entity_id = Column(String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    absorbed_entity_id = Column(String(36), nullable=False, index=True)
    absorbed_entity_data = Column(JSON, nullable=False)
    merged_by = Column(String(128), default="Analyst")
    merge_reason = Column(Text, nullable=True)
    match_score = Column(Float, default=1.0)
    is_active = Column(Boolean, default=True, index=True)
    merged_at = Column(DateTime, default=datetime.utcnow, index=True)
    unmerged_at = Column(DateTime, nullable=True)
    unmerged_by = Column(String(128), nullable=True)

    # Relationships
    canonical_entity = relationship("EntityModel", back_populates="merge_logs", foreign_keys=[canonical_entity_id], passive_deletes=True)


