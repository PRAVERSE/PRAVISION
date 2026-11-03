import asyncio
import json
import hashlib
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, desc
from sqlalchemy.orm import selectinload

from app.storage.database import async_session_maker
from app.storage.models_db import (
    CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel, AuditLogModel,
    CaseMembershipModel, UserModel
)
from app.storage.b2_storage import b2_storage
from app.evidence.models import EvidenceFinding, EntityType

logger = logging.getLogger("pravision.storage.case_manager")

class CaseManager:
    """
    Manages persistent case dossiers, persistent investigations,
    evidence vault associations, and cross-case intelligence querying.
    """

    async def create_case(
        self,
        title: str,
        description: Optional[str] = None,
        created_by: str = "Analyst",
        owner_id: Optional[str] = None,
        classification: str = "UNCLASSIFIED",
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        case_num = f"CASE-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        case_id = str(uuid.uuid4())
        async with async_session_maker() as session:
            case = CaseModel(
                id=case_id,
                case_number=case_num,
                title=title,
                description=description,
                created_by=created_by,
                owner_id=owner_id,
                classification=classification,
                tags=tags or []
            )
            session.add(case)
            
            # Log audit
            audit = AuditLogModel(
                user=created_by,
                actor_id=owner_id,
                action="create_case",
                target_type="case",
                target_id=case_id,
                details={"case_number": case_num, "title": title}
            )
            session.add(audit)
            await session.commit()
            await session.refresh(case)
            return self._case_to_dict(case)

    async def list_cases(
        self,
        limit: int = 50,
        offset: int = 0,
        user_id: Optional[str] = None,
        role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        async with async_session_maker() as session:
            stmt = select(CaseModel).order_by(desc(CaseModel.created_at))
            if role and role != "admin" and user_id:
                # Filter cases where user is owner or explicit member
                stmt = stmt.outerjoin(CaseMembershipModel, CaseModel.id == CaseMembershipModel.case_id).where(
                    (CaseModel.owner_id == user_id) | (CaseMembershipModel.user_id == user_id)
                ).distinct()
            stmt = stmt.offset(offset).limit(limit)
            result = await session.execute(stmt)
            cases = result.scalars().all()
            return [self._case_to_dict(c) for c in cases]

    async def share_case(self, case_id: str, user_id: str, permission: str = "read", granted_by: Optional[str] = None) -> Dict[str, Any]:
        """Grants or updates user access to a specific case."""
        async with async_session_maker() as session:
            stmt = select(CaseMembershipModel).where(
                CaseMembershipModel.case_id == case_id,
                CaseMembershipModel.user_id == user_id
            )
            membership = (await session.execute(stmt)).scalar_one_or_none()
            if membership:
                membership.permission = permission
            else:
                membership = CaseMembershipModel(
                    case_id=case_id,
                    user_id=user_id,
                    permission=permission,
                    granted_by=granted_by
                )
                session.add(membership)
            
            audit = AuditLogModel(
                user=granted_by or "system",
                actor_id=granted_by,
                action="share_case",
                target_type="case",
                target_id=case_id,
                details={"shared_with_user_id": user_id, "permission": permission}
            )
            session.add(audit)
            await session.commit()
            return {"status": "shared", "case_id": case_id, "user_id": user_id, "permission": permission}

    async def revoke_case_share(self, case_id: str, user_id: str, revoked_by: Optional[str] = None) -> bool:
        """Revokes a user's access to a specific case."""
        async with async_session_maker() as session:
            stmt = select(CaseMembershipModel).where(
                CaseMembershipModel.case_id == case_id,
                CaseMembershipModel.user_id == user_id
            )
            membership = (await session.execute(stmt)).scalar_one_or_none()
            if not membership:
                return False
            await session.delete(membership)
            audit = AuditLogModel(
                user=revoked_by or "system",
                actor_id=revoked_by,
                action="revoke_case_share",
                target_type="case",
                target_id=case_id,
                details={"revoked_user_id": user_id}
            )
            session.add(audit)
            await session.commit()
            return True

    async def list_case_members(self, case_id: str) -> List[Dict[str, Any]]:
        """Lists users with granted access to a case."""
        async with async_session_maker() as session:
            stmt = select(CaseMembershipModel).options(selectinload(CaseMembershipModel.user)).where(
                CaseMembershipModel.case_id == case_id
            )
            members = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "membership_id": m.id,
                    "user_id": m.user_id,
                    "username": m.user.username if m.user else "Unknown",
                    "role": m.user.role if m.user else "analyst",
                    "permission": m.permission,
                    "granted_at": m.granted_at.isoformat() if m.granted_at else None
                }
                for m in members
            ]

    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        async with async_session_maker() as session:
            stmt = select(CaseModel).options(
                selectinload(CaseModel.investigations),
                selectinload(CaseModel.entities),
                selectinload(CaseModel.evidences)
            ).where(CaseModel.id == case_id)
            result = await session.execute(stmt)
            case = result.scalar_one_or_none()
            if not case:
                return None
            
            d = self._case_to_dict(case)
            d["investigations"] = [self._investigation_to_dict(inv) for inv in case.investigations]
            d["entities_count"] = len(case.entities)
            d["evidence_count"] = len(case.evidences)
            return d

    async def save_investigation_to_case(
        self,
        case_id: str,
        investigation_id: str,
        root_input: str,
        root_type: str,
        mode: str,
        findings: List[EvidenceFinding],
        graph_nodes: Optional[List[Dict[str, Any]]] = None,
        graph_edges: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Persists an active memory investigation into a designated case dossier.
        """
        graph_nodes = graph_nodes or []
        graph_edges = graph_edges or []
        async with async_session_maker() as session:
            # Check case exists
            stmt = select(CaseModel).where(CaseModel.id == case_id)
            res = await session.execute(stmt)
            case = res.scalar_one_or_none()
            if not case:
                raise ValueError(f"Case with ID '{case_id}' does not exist.")

            inv = InvestigationModel(
                id=investigation_id,
                case_id=case_id,
                root_input=root_input,
                root_type=root_type,
                mode=mode,
                status="completed",
                total_findings=len(findings),
                verified_relationships=len(graph_edges),
                completed_at=datetime.utcnow()
            )
            session.add(inv)

            # Map and store unique entities
            entity_id_map: Dict[str, str] = {}
            ent_models = []
            for node in graph_nodes:
                node_id = str(node.get("id")) if node.get("id") is not None else None
                ent_val = str(node.get("label") or node.get("id") or "")
                ent_type = node.get("type", "unknown")
                ent_norm = ent_val.strip().lower()
                ent_id = str(uuid.uuid4())
                
                ent_model = EntityModel(
                    id=ent_id,
                    investigation_id=investigation_id,
                    case_id=case_id,
                    entity_type=ent_type,
                    entity_value=ent_val,
                    normalized_value=ent_norm,
                    confidence=node.get("confidence", "moderate"),
                    properties=node
                )
                ent_models.append(ent_model)
                entity_id_map[ent_val] = ent_id
                if node_id:
                    entity_id_map[node_id] = ent_id

            if ent_models:
                session.add_all(ent_models)

            # Flush to persist entities and verify integrity
            await session.flush()

            # Map and store relationships
            rel_models = []
            for edge in graph_edges:
                src_val = str(edge.get("source") or "")
                tgt_val = str(edge.get("target") or "")
                src_id = entity_id_map.get(src_val)
                tgt_id = entity_id_map.get(tgt_val)

                if src_id and tgt_id:
                    rel_id = str(uuid.uuid4())
                    rel_model = RelationshipModel(
                        id=rel_id,
                        investigation_id=investigation_id,
                        source_id=src_id,
                        target_id=tgt_id,
                        relationship_type=edge.get("relationship", "CONNECTED_TO"),
                        confidence=edge.get("confidence", "moderate"),
                        properties=edge
                    )
                    rel_models.append(rel_model)

            if rel_models:
                session.add_all(rel_models)

            # Store evidence items
            ev_models = []
            for f in findings:
                ent_id = entity_id_map.get(f.entity_value)
                payload = f.raw_payload or {}
                f_key = payload.get("file_key") or payload.get("b2_file_key")
                f_hash = payload.get("file_hash") or payload.get("sha256")
                f_size = payload.get("file_size") or payload.get("size", 0)
                f_mime = payload.get("mime_type") or payload.get("content_type", "application/json")
                backend_type = "neon_cloud" if b2_storage.is_neon else ("b2_cloud" if b2_storage.is_cloud_enabled else "database")
                
                ev_model = EvidenceModel(
                    id=f.id,
                    investigation_id=investigation_id,
                    case_id=case_id,
                    entity_id=ent_id,
                    connector_name=f.source_name,
                    source_url=f.source_url,
                    raw_data=payload,
                    file_mime_type=f_mime,
                    file_hash=f_hash,
                    file_size=f_size,
                    b2_file_key=f_key,
                    storage_backend=backend_type if f_key else "database",
                    collected_at=f.collection_timestamp
                )
                ev_models.append(ev_model)

            if ev_models:
                session.add_all(ev_models)

            # Audit log
            audit = AuditLogModel(
                action="save_investigation_to_case",
                target_type="investigation",
                target_id=investigation_id,
                details={"case_id": case_id, "findings_count": len(findings)}
            )
            session.add(audit)

            case.updated_at = datetime.utcnow()
            await session.commit()
            logger.info(f"Successfully saved investigation {investigation_id} to case {case_id}")
            return {"status": "saved", "case_id": case_id, "investigation_id": investigation_id}

    async def attach_evidence(
        self,
        case_id: str,
        file_key: str,
        file_hash: str,
        file_size: int,
        file_mime_type: str = "application/octet-stream",
        connector_name: str = "evidence_vault",
        investigation_id: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Directly attaches a verified evidence file to a case dossier."""
        async with async_session_maker() as session:
            ev_id = str(uuid.uuid4())
            ev = EvidenceModel(
                id=ev_id,
                case_id=case_id,
                investigation_id=investigation_id,
                entity_id=entity_id,
                connector_name=connector_name,
                b2_file_key=file_key,
                file_hash=file_hash,
                file_size=file_size,
                file_mime_type=file_mime_type,
                storage_backend="neon_cloud" if b2_storage.is_neon else "local_vault",
                raw_data={"attached_manually": True}
            )
            session.add(ev)
            await session.commit()
            return {"status": "attached", "evidence_id": ev_id, "case_id": case_id}

    async def delete_case(self, case_id: str, delete_evidence_files: bool = True) -> bool:
        s3_keys_to_delete = []
        async with async_session_maker() as session:
            stmt = select(CaseModel).options(selectinload(CaseModel.evidences)).where(CaseModel.id == case_id)
            res = await session.execute(stmt)
            case = res.scalar_one_or_none()
            if not case:
                return False

            # Collect associated evidence files to delete outside the DB transaction
            if delete_evidence_files and case.evidences:
                s3_keys_to_delete = [ev.b2_file_key for ev in case.evidences if ev.b2_file_key]
            
            await session.delete(case)
            audit = AuditLogModel(
                action="delete_case",
                target_type="case",
                target_id=case_id,
                details={"case_number": case.case_number, "evidence_deleted": delete_evidence_files}
            )
            session.add(audit)
            await session.commit()

        # Delete associated evidence files concurrently outside DB transaction
        if s3_keys_to_delete:
            delete_tasks = [b2_storage.delete_evidence(k) for k in s3_keys_to_delete]
            await asyncio.gather(*delete_tasks, return_exceptions=True)
            logger.info(f"Concurrently deleted {len(s3_keys_to_delete)} storage file(s) for case {case_id}")

        return True

    async def export_case_dossier(self, case_id: str) -> Dict[str, Any]:
        """
        Exports an entire case dossier, child investigations, entities, relationships,
        and evidence metadata as a cryptographically verifiable JSON package for backup.
        """
        async with async_session_maker() as session:
            stmt = select(CaseModel).options(
                selectinload(CaseModel.investigations).selectinload(InvestigationModel.relationships),
                selectinload(CaseModel.entities),
                selectinload(CaseModel.evidences)
            ).where(CaseModel.id == case_id)
            res = await session.execute(stmt)
            case = res.scalar_one_or_none()
            if not case:
                raise ValueError(f"Case with ID '{case_id}' does not exist.")

            # Load audit logs
            stmt_audit = select(AuditLogModel).where(AuditLogModel.target_id == case_id)
            audits = (await session.execute(stmt_audit)).scalars().all()

            invs_data = []
            rels_data = []
            for inv in case.investigations:
                inv_dict = self._investigation_to_dict(inv)
                invs_data.append(inv_dict)
                for rel in (inv.relationships or []):
                    rels_data.append({
                        "id": rel.id,
                        "investigation_id": rel.investigation_id,
                        "source_id": rel.source_id,
                        "target_id": rel.target_id,
                        "relationship_type": rel.relationship_type,
                        "confidence": rel.confidence,
                        "properties": rel.properties or {}
                    })

            ents_data = [
                {
                    "id": e.id,
                    "investigation_id": e.investigation_id,
                    "entity_type": e.entity_type,
                    "entity_value": e.entity_value,
                    "normalized_value": e.normalized_value,
                    "confidence": e.confidence,
                    "properties": e.properties or {}
                }
                for e in case.entities
            ]

            evs_data = [
                {
                    "id": ev.id,
                    "investigation_id": ev.investigation_id,
                    "entity_id": ev.entity_id,
                    "connector_name": ev.connector_name,
                    "source_url": ev.source_url,
                    "raw_data": ev.raw_data or {},
                    "b2_file_key": ev.b2_file_key,
                    "file_hash": ev.file_hash,
                    "file_mime_type": ev.file_mime_type,
                    "file_size": ev.file_size,
                    "storage_backend": ev.storage_backend,
                    "collected_at": ev.collected_at.isoformat() if ev.collected_at else None
                }
                for ev in case.evidences
            ]

            audits_data = [
                {
                    "action": a.action,
                    "user": a.user,
                    "target_type": a.target_type,
                    "target_id": a.target_id,
                    "details": a.details or {},
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None
                }
                for a in audits
            ]

            package = {
                "format_version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "case": self._case_to_dict(case),
                "investigations": invs_data,
                "entities": ents_data,
                "relationships": rels_data,
                "evidences": evs_data,
                "audit_logs": audits_data
            }

            raw_str = json.dumps(package, sort_keys=True)
            package["checksum_sha256"] = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()
            return package

    async def import_case_dossier(self, dossier_data: Dict[str, Any], generate_new_ids: bool = False) -> Dict[str, Any]:
        """
        Imports and restores a previously exported case dossier package into the database.
        """
        case_data = dossier_data.get("case", {})
        if not case_data.get("case_number"):
            raise ValueError("Invalid dossier package: missing case metadata.")

        async with async_session_maker() as session:
            case_id = str(uuid.uuid4()) if generate_new_ids else case_data["id"]
            case_num = f"RESTORED-{case_data['case_number']}" if generate_new_ids else case_data["case_number"]

            # Create case model
            case = CaseModel(
                id=case_id,
                case_number=case_num,
                title=case_data.get("title", "Restored Case"),
                description=case_data.get("description"),
                created_by=case_data.get("created_by", "Restoration Agent"),
                status=case_data.get("status", "active"),
                classification=case_data.get("classification", "UNCLASSIFIED"),
                tags=case_data.get("tags", [])
            )
            session.add(case)

            # Map IDs if generating new IDs
            id_map: Dict[str, str] = {}
            if generate_new_ids:
                id_map[case_data["id"]] = case_id

            # Restore investigations
            inv_models = []
            for inv in dossier_data.get("investigations", []):
                old_id = inv["id"]
                new_id = str(uuid.uuid4()) if generate_new_ids else old_id
                id_map[old_id] = new_id
                inv_models.append(InvestigationModel(
                    id=new_id,
                    case_id=case_id,
                    root_input=inv["root_input"],
                    root_type=inv["root_type"],
                    mode=inv["mode"],
                    status=inv.get("status", "completed"),
                    total_findings=inv.get("total_findings", 0),
                    verified_relationships=inv.get("verified_relationships", 0)
                ))
            if inv_models:
                session.add_all(inv_models)

            # Restore entities
            ent_models = []
            for ent in dossier_data.get("entities", []):
                old_ent_id = ent["id"]
                new_ent_id = str(uuid.uuid4()) if generate_new_ids else old_ent_id
                id_map[old_ent_id] = new_ent_id
                target_inv_id = id_map.get(ent.get("investigation_id"), ent.get("investigation_id"))
                ent_models.append(EntityModel(
                    id=new_ent_id,
                    case_id=case_id,
                    investigation_id=target_inv_id,
                    entity_type=ent["entity_type"],
                    entity_value=ent["entity_value"],
                    normalized_value=ent.get("normalized_value", ent["entity_value"].strip().lower()),
                    confidence=ent.get("confidence", "moderate"),
                    properties=ent.get("properties", {})
                ))
            if ent_models:
                session.add_all(ent_models)

            # Restore relationships
            rel_models = []
            for rel in dossier_data.get("relationships", []):
                target_inv_id = id_map.get(rel.get("investigation_id"), rel.get("investigation_id"))
                new_src = id_map.get(rel["source_id"], rel["source_id"])
                new_tgt = id_map.get(rel["target_id"], rel["target_id"])
                rel_models.append(RelationshipModel(
                    id=str(uuid.uuid4()) if generate_new_ids else rel["id"],
                    investigation_id=target_inv_id,
                    source_id=new_src,
                    target_id=new_tgt,
                    relationship_type=rel["relationship_type"],
                    confidence=rel.get("confidence", "moderate"),
                    properties=rel.get("properties", {})
                ))
            if rel_models:
                session.add_all(rel_models)

            # Restore evidences
            ev_models = []
            for ev in dossier_data.get("evidences", []):
                target_inv_id = id_map.get(ev.get("investigation_id"), ev.get("investigation_id"))
                target_ent_id = id_map.get(ev.get("entity_id"), ev.get("entity_id"))
                ev_models.append(EvidenceModel(
                    id=str(uuid.uuid4()) if generate_new_ids else ev["id"],
                    case_id=case_id,
                    investigation_id=target_inv_id,
                    entity_id=target_ent_id,
                    connector_name=ev["connector_name"],
                    source_url=ev.get("source_url"),
                    raw_data=ev.get("raw_data", {}),
                    b2_file_key=ev.get("b2_file_key"),
                    file_hash=ev.get("file_hash"),
                    file_mime_type=ev.get("file_mime_type"),
                    file_size=ev.get("file_size", 0),
                    storage_backend=ev.get("storage_backend", "neon_cloud")
                ))
            if ev_models:
                session.add_all(ev_models)

            # Audit log
            audit = AuditLogModel(
                action="import_case_dossier",
                target_type="case",
                target_id=case_id,
                details={"source_case_number": case_data.get("case_number"), "restored_at": datetime.utcnow().isoformat()}
            )
            session.add(audit)
            await session.commit()
            return {"status": "imported", "case_id": case_id, "case_number": case_num}

    def _case_to_dict(self, c: CaseModel) -> Dict[str, Any]:
        return {
            "id": c.id,
            "case_id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "description": c.description,
            "created_by": c.created_by,
            "owner_id": c.owner_id,
            "status": c.status,
            "classification": c.classification,
            "tags": c.tags or [],
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }

    def _investigation_to_dict(self, inv: InvestigationModel) -> Dict[str, Any]:
        return {
            "id": inv.id,
            "case_id": inv.case_id,
            "root_input": inv.root_input,
            "root_type": inv.root_type,
            "mode": inv.mode,
            "status": inv.status,
            "total_findings": inv.total_findings,
            "verified_relationships": inv.verified_relationships,
            "created_at": inv.created_at.isoformat() if inv.created_at else None,
            "completed_at": inv.completed_at.isoformat() if inv.completed_at else None,
        }

case_manager = CaseManager()

