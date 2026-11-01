from typing import List
from app.evidence.models import EvidenceFinding, EntityType
from app.engine.discovery_queue import DiscoveryItem
from app.evidence.evidence_validator import evidence_validator

class ExpansionEngine:
    """
    Extracts high-value, authorized secondary entities from evidence findings
    to enable intelligent recursive investigation.
    """

    def extract_expansion_candidates(self, finding: EvidenceFinding, current_depth: int) -> List[DiscoveryItem]:
        candidates: List[DiscoveryItem] = []

        # 1. From discovered domains or subdomains -> Resolve DNS / Tech stack
        if finding.entity_type in (EntityType.DOMAIN, EntityType.SUBDOMAIN):
            val = finding.entity_value.strip().lower()
            if evidence_validator.validate(EntityType.DOMAIN, val):
                candidates.append(DiscoveryItem(
                    entity_value=val,
                    entity_type=finding.entity_type,
                    depth=current_depth + 1,
                    parent_entity=finding.entity_value,
                    discovered_by=finding.source_name
                ))

        # 2. From extracted GPS coordinates -> Geocode and compute solar shadows
        elif finding.entity_type == EntityType.GEO_COORDINATE:
            candidates.append(DiscoveryItem(
                entity_value=finding.entity_value,
                entity_type=EntityType.GEO_COORDINATE,
                depth=current_depth + 1,
                parent_entity=finding.entity_value,
                discovered_by=finding.source_name
            ))

        # 3. From resolved IP addresses -> Passive ASN / Org resolution
        elif finding.entity_type == EntityType.IP_ADDRESS:
            val = finding.entity_value.strip()
            if evidence_validator.validate(EntityType.IP_ADDRESS, val):
                candidates.append(DiscoveryItem(
                    entity_value=val,
                    entity_type=EntityType.IP_ADDRESS,
                    depth=current_depth + 1,
                    parent_entity=finding.entity_value,
                    discovered_by=finding.source_name
                ))

        # 4. From secondary related entities (e.g. MX host domains, corporate domains)
        for rel in finding.related_entities:
            if rel and "." in rel and not rel.startswith("http") and "@" not in rel:
                rel_clean = rel.strip().lower()
                if evidence_validator.validate(EntityType.DOMAIN, rel_clean):
                    candidates.append(DiscoveryItem(
                        entity_value=rel_clean,
                        entity_type=EntityType.DOMAIN,
                        depth=current_depth + 1,
                        parent_entity=finding.entity_value,
                        discovered_by=finding.source_name
                    ))

        return candidates

expansion_engine = ExpansionEngine()
