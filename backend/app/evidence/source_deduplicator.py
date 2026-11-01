from typing import List, Dict
from app.evidence.models import EvidenceFinding, EntityType

class SourceDeduplicator:
    """
    Normalizes entities and merges redundant evidence items into clean unified records.
    """

    @staticmethod
    def normalize_value(entity_type: EntityType, value: str) -> str:
        val = value.strip()
        if entity_type in (EntityType.EMAIL, EntityType.DOMAIN, EntityType.SUBDOMAIN, EntityType.USERNAME):
            return val.lower()
        if entity_type == EntityType.HASH:
            return val.lower()
        if entity_type == EntityType.PHONE:
            return "".join(c for c in val if c.isdigit() or c == '+')
        if entity_type == EntityType.URL:
            return val.rstrip('/')
        return val

    def deduplicate(self, findings: List[EvidenceFinding]) -> List[EvidenceFinding]:
        seen_signatures: Dict[str, EvidenceFinding] = {}

        for finding in findings:
            norm_val = self.normalize_value(finding.entity_type, finding.entity_value)
            signature = f"{finding.entity_type}:{norm_val}"

            if signature in seen_signatures:
                existing = seen_signatures[signature]
                # Merge supporting sources
                if finding.source_name and finding.source_name not in existing.supporting_sources:
                    existing.supporting_sources.append(finding.source_name)
                # Merge any new related entities
                for rel in finding.related_entities:
                    if rel not in existing.related_entities:
                        existing.related_entities.append(rel)
                # Keep highest match_type
                if existing.match_type != finding.match_type and finding.match_type.value == "exact_match":
                    existing.match_type = finding.match_type
            else:
                finding.entity_value = norm_val
                if finding.source_name and finding.source_name not in finding.supporting_sources:
                    finding.supporting_sources.append(finding.source_name)
                seen_signatures[signature] = finding

        return list(seen_signatures.values())

source_deduplicator = SourceDeduplicator()
