from typing import List, Set
from app.evidence.models import EvidenceFinding, EntityType
from app.engine.discovery_queue import DiscoveryItem
from app.evidence.evidence_validator import evidence_validator

# Domains that must never be expanded into recursive infrastructure scans
EXCLUDED_EXPANSION_DOMAINS: Set[str] = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "msn.com", "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com",
    "aol.com", "zoho.com", "zoho.eu", "gmx.com", "gmx.net", "mail.com", "yandex.com",
    "yandex.ru", "fastmail.com", "tutanota.com", "tuta.com", "mailinator.com", "tempmail.com",
    "guerrillamail.com", "10minutemail.com", "throwawaymail.com", "sharklasers.com",
    "google.com", "microsoft.com", "apple.com"
}

def is_excluded_domain(domain: str) -> bool:
    dom = domain.strip().lower()
    if dom in EXCLUDED_EXPANSION_DOMAINS:
        return True
    if any(dom.endswith("." + excl) for excl in EXCLUDED_EXPANSION_DOMAINS):
        return True
    if dom.endswith(".google.com") or dom.endswith(".outlook.com") or dom.endswith(".yahoodns.net") or dom.endswith(".pphosted.com"):
        return True
    return False

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
            if not is_excluded_domain(val) and evidence_validator.validate(EntityType.DOMAIN, val):
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
                if not is_excluded_domain(rel_clean) and evidence_validator.validate(EntityType.DOMAIN, rel_clean):
                    candidates.append(DiscoveryItem(
                        entity_value=rel_clean,
                        entity_type=EntityType.DOMAIN,
                        depth=current_depth + 1,
                        parent_entity=finding.entity_value,
                        discovered_by=finding.source_name
                    ))

        return candidates

expansion_engine = ExpansionEngine()


