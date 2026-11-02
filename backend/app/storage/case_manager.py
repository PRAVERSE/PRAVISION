import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, update, delete, desc
from sqlalchemy.orm import selectinload

from app.storage.database import async_session_maker
from app.storage.models_db import CaseModel, InvestigationModel, EntityModel, RelationshipModel, EvidenceModel, AuditLogModel
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
        classification: str = "UNCLASSIFIED",
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        case_num = f"CASE-{datetime.utcnow().strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"
        async with async_session_maker() as session:
            case = CaseModel(
                case_number=case_num,
                title=title,
                description=description,
                created_by=created_by,
                classification=classification,
                tags=tags or []
            )
            session.add(case)
            
            # Log audit
            audit = AuditLogModel(
                user=created_by,
                action="create_case",
                target_type="case",
                target_id=case.id,
                details={"case_number": case_num, "title": title}
            )
            session.add(audit)
            await session.commit()
            await session.refresh(case)
            return self._case_to_dict(case)

    async def list_cases(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        async with async_session_maker() as session:
            stmt = select(CaseModel).order_by(desc(CaseModel.created_at)).offset(offset).limit(limit)
            result = await session.execute(stmt)
            cases = result.scalars().all()
            return [self._case_to_dict(c) for c in cases]

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
        graph_nodes: List[Dict[str, Any]],
        graph_edges: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Persists an active memory investigation into a designated case dossier.
        """
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
            for node in graph_nodes:
                ent_val = node.get("label") or node.get("id")
                ent_type = node.get("type", "unknown")
                ent_norm = ent_val.strip().lower()
                
                ent_model = EntityModel(
                    investigation_id=investigation_id,
                    case_id=case_id,
                    entity_type=ent_type,
                    entity_value=ent_val,
                    normalized_value=ent_norm,
                    confidence=node.get("confidence", "moderate"),
                    properties=node
                )
                session.add(ent_model)
                entity_id_map[ent_val] = ent_model.id

            # Flush to get entity IDs
            await session.flush()

            # Map and store relationships
            for edge in graph_edges:
                src_val = edge.get("source")
                tgt_val = edge.get("target")
                src_id = entity_id_map.get(src_val)
                tgt_id = entity_id_map.get(tgt_val)

                if src_id and tgt_id:
                    rel_model = RelationshipModel(
                        investigation_id=investigation_id,
                        source_id=src_id,
                        target_id=tgt_id,
                        relationship_type=edge.get("relationship", "CONNECTED_TO"),
                        confidence=edge.get("confidence", "moderate"),
                        properties=edge
                    )
                    session.add(rel_model)

            # Store evidence items
            for f in findings:
                ent_id = entity_id_map.get(f.entity_value)
                ev_model = EvidenceModel(
                    id=f.id,
                    investigation_id=investigation_id,
                    case_id=case_id,
                    entity_id=ent_id,
                    connector_name=f.source_name,
                    source_url=f.source_url,
                    raw_data=f.raw_payload or {},
                    file_mime_type="application/json",
                    storage_backend="database",
                    collected_at=f.collection_timestamp
                )
                session.add(ev_model)

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

    async def delete_case(self, case_id: str) -> bool:
        async with async_session_maker() as session:
            stmt = select(CaseModel).where(CaseModel.id == case_id)
            res = await session.execute(stmt)
            case = res.scalar_one_or_none()
            if not case:
                return False
            
            await session.delete(case)
            audit = AuditLogModel(
                action="delete_case",
                target_type="case",
                target_id=case_id,
                details={"case_number": case.case_number}
            )
            session.add(audit)
            await session.commit()
            return True

    def _case_to_dict(self, c: CaseModel) -> Dict[str, Any]:
        return {
            "id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "description": c.description,
            "created_by": c.created_by,
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
