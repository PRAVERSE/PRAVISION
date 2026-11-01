import re
import ipaddress
from app.evidence.models import EntityType

class EvidenceValidator:
    """Validates syntax and structure of evidence entities before expansion."""

    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
    DOMAIN_REGEX = re.compile(r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$')
    USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_\-\.]{2,50}$')
    HASH_MD5 = re.compile(r'^[a-fA-F0-9]{32}$')
    HASH_SHA1 = re.compile(r'^[a-fA-F0-9]{40}$')
    HASH_SHA256 = re.compile(r'^[a-fA-F0-9]{64}$')

    @classmethod
    def validate(cls, entity_type: EntityType, value: str) -> bool:
        v = value.strip()
        if not v:
            return False

        if entity_type == EntityType.EMAIL:
            return bool(cls.EMAIL_REGEX.match(v))

        if entity_type in (EntityType.DOMAIN, EntityType.SUBDOMAIN):
            return bool(cls.DOMAIN_REGEX.match(v))

        if entity_type == EntityType.IP_ADDRESS:
            try:
                ipaddress.ip_address(v)
                return True
            except ValueError:
                return False

        if entity_type == EntityType.USERNAME:
            return bool(cls.USERNAME_REGEX.match(v))

        if entity_type == EntityType.HASH:
            return bool(cls.HASH_MD5.match(v) or cls.HASH_SHA1.match(v) or cls.HASH_SHA256.match(v))

        if entity_type == EntityType.PHONE:
            cleaned = "".join(c for c in v if c.isdigit() or c == '+')
            return len(cleaned) >= 7 and len(cleaned) <= 17

        if entity_type == EntityType.URL:
            return v.startswith("http://") or v.startswith("https://")

        return True

evidence_validator = EvidenceValidator()
