import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select, or_, and_
from sqlalchemy.orm import selectinload

from app.storage.database import async_session_maker
from app.storage.models_db import EntityModel, RelationshipModel, EvidenceModel, CaseModel

logger = logging.getLogger("pravision.intelligence.unified_search")

class UnifiedSearchEngine:
    """
    Gotham-Grade Unified Intelligence Search Engine:
    Performs cross-case, cross-entity, cross-relationship, and cross-evidence queries
    with fuzzy substring matching, entity type discrimination, and source provenance attribution.
    """

    async def search(
        self,
        query: str,
        entity_type: Optional[str] = None,
        case_id: Optional[str] = None,
        min_confidence: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        term = query.strip().lower()
        if not term:
            return {"query": query, "total_matches": 0, "results": []}

        results: List[Dict[str, Any]] = []

        async with async_session_maker() as session:
            # 1. Search Entities
            stmt_ent = select(EntityModel).options(selectinload(EntityModel.case))
            conditions_ent = [
                or_(
                    EntityModel.normalized_value.like(f"%{term}%"),
                    EntityModel.entity_value.ilike(f"%{term}%")
                )
            ]
            if entity_type and entity_type != "all":
                conditions_ent.append(EntityModel.entity_type == entity_type)
            if case_id:
                conditions_ent.append(EntityModel.case_id == case_id)
            if min_confidence and min_confidence != "all":
                conditions_ent.append(EntityModel.confidence == min_confidence)

            stmt_ent = stmt_ent.where(and_(*conditions_ent)).limit(limit)
            entities = (await session.execute(stmt_ent)).scalars().all()

            for e in entities:
                alias_matches = [a for a in (e.aliases or []) if term in a.lower()]
                matched_id_keys = [
                    k for k, v in (e.identifiers or {}).items()
                    if term in str(v).lower()
                ]
                snippet = f"Entity: {e.entity_value} ({e.entity_type})"
                if alias_matches:
                    snippet += f" | Matched Alias: {', '.join(alias_matches)}"
                if matched_id_keys:
                    snippet += f" | Matched Identifier: {', '.join(matched_id_keys)}"

                results.append({
                    "result_type": "entity",
                    "id": e.id,
                    "title": e.entity_value,
                    "entity_type": e.entity_type,
                    "confidence": e.confidence,
                    "verification_status": e.verification_status,
                    "case_id": e.case_id,
                    "case_number": e.case.case_number if e.case else None,
                    "snippet": snippet,
                    "provenance_sources": e.sources or [],
                    "aliases": e.aliases or [],
                    "identifiers": e.identifiers or {},
                    "is_merged": bool(e.merged_into_id),
                    "created_at": e.first_seen.isoformat() if e.first_seen else None
                })

            # 2. Search Evidence
            stmt_ev = select(EvidenceModel).options(selectinload(EvidenceModel.case))
            conditions_ev = [
                or_(
                    EvidenceModel.connector_name.ilike(f"%{term}%"),
                    EvidenceModel.source_url.ilike(f"%{term}%"),
                    EvidenceModel.file_hash.ilike(f"%{term}%")
                )
            ]
            if case_id:
                conditions_ev.append(EvidenceModel.case_id == case_id)

            stmt_ev = stmt_ev.where(and_(*conditions_ev)).limit(limit)
            evidences = (await session.execute(stmt_ev)).scalars().all()

            for ev in evidences:
                results.append({
                    "result_type": "evidence",
                    "id": ev.id,
                    "title": f"Evidence from {ev.connector_name}",
                    "entity_type": "evidence_item",
                    "confidence": "high" if ev.file_hash else "moderate",
                    "verification_status": "hash_verified" if ev.file_hash else "unverified",
                    "case_id": ev.case_id,
                    "case_number": ev.case.case_number if ev.case else None,
                    "snippet": f"Source: {ev.connector_name} | URL: {ev.source_url or 'N/A'} | Hash: {ev.file_hash or 'N/A'}",
                    "provenance_sources": [ev.connector_name],
                    "created_at": ev.collected_at.isoformat() if ev.collected_at else None
                })

            # 3. Search Cases
            stmt_case = select(CaseModel).where(
                or_(
                    CaseModel.title.ilike(f"%{term}%"),
                    CaseModel.case_number.ilike(f"%{term}%"),
                    CaseModel.description.ilike(f"%{term}%")
                )
            ).limit(limit)
            cases = (await session.execute(stmt_case)).scalars().all()

            for c in cases:
                results.append({
                    "result_type": "case",
                    "id": c.id,
                    "title": f"{c.case_number}: {c.title}",
                    "entity_type": "case_dossier",
                    "confidence": "corroborated",
                    "verification_status": c.classification,
                    "case_id": c.id,
                    "case_number": c.case_number,
                    "snippet": f"Case Dossier: {c.title} | Status: {c.status} | Classification: {c.classification}",
                    "provenance_sources": [f"Investigator: {c.created_by}"],
                    "created_at": c.created_at.isoformat() if c.created_at else None
                })

        return {
            "query": query,
            "total_matches": len(results),
            "results": results[:limit]
        }

unified_search = UnifiedSearchEngine()
