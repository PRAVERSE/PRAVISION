import re
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from app.evidence.models import EvidenceFinding, EntityType, MatchType, ConfidenceLevel

logger = logging.getLogger("pravision.intelligence.entity_resolution")

class EntityResolutionEngine:
    """
    Gotham-style Entity Resolution Engine:
    Resolves mentions, detects identity duplicates, calculates confidence corroborate scores,
    and identifies contradictions across multi-source OSINT evidence.
    """

    @staticmethod
    def normalize_string(s: str) -> str:
        return re.sub(r'[\s\-_\.@]+', '', s.strip().lower())

    @staticmethod
    def jaro_winkler_similarity(s1: str, s2: str) -> float:
        """Calculates Jaro-Winkler string similarity (0.0 to 1.0)."""
        if s1 == s2:
            return 1.0
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0

        match_distance = max(len1, len2) // 2 - 1
        matches1 = [False] * len1
        matches2 = [False] * len2
        matches = 0

        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            for j in range(start, end):
                if matches2[j] or s1[i] != s2[j]:
                    continue
                matches1[i] = True
                matches2[j] = True
                matches += 1
                break

        if matches == 0:
            return 0.0

        transpositions = 0
        k = 0
        for i in range(len1):
            if not matches1[i]:
                continue
            while not matches2[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1

        m = float(matches)
        jaro = ((m / len1) + (m / len2) + ((m - transpositions / 2.0) / m)) / 3.0

        # Winkler prefix bonus (up to 4 chars)
        prefix_len = 0
        for i in range(min(4, len1, len2)):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break

        return jaro + (prefix_len * 0.1 * (1.0 - jaro))

    def compare_entities(
        self,
        val1: str,
        type1: EntityType,
        val2: str,
        type2: EntityType,
        props1: Optional[Dict[str, Any]] = None,
        props2: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Compares two entity candidates and determines match confidence and potential contradictions.
        """
        # Exact match
        if type1 == type2 and val1.strip().lower() == val2.strip().lower():
            return {
                "match_type": MatchType.EXACT_MATCH,
                "score": 1.0,
                "is_match": True,
                "reason": f"Exact value match for {type1.value}",
                "contradictions": []
            }

        # Email & Username correlation
        if (type1 == EntityType.EMAIL and type2 == EntityType.USERNAME) or (type1 == EntityType.USERNAME and type2 == EntityType.EMAIL):
            email = val1 if type1 == EntityType.EMAIL else val2
            user = val2 if type1 == EntityType.EMAIL else val1
            email_prefix = email.split("@")[0].lower()
            sim = self.jaro_winkler_similarity(self.normalize_string(email_prefix), self.normalize_string(user))
            if sim >= 0.88:
                return {
                    "match_type": MatchType.HEURISTIC_MATCH,
                    "score": round(sim, 3),
                    "is_match": True,
                    "reason": f"Email username '{email_prefix}' matches profile username '{user}'",
                    "contradictions": []
                }

        # Domain & Subdomain correlation
        if (type1 == EntityType.DOMAIN and type2 == EntityType.SUBDOMAIN) or (type1 == EntityType.SUBDOMAIN and type2 == EntityType.DOMAIN):
            sub = val1 if type1 == EntityType.SUBDOMAIN else val2
            dom = val2 if type1 == EntityType.SUBDOMAIN else val1
            if sub.lower().endswith(dom.lower()):
                return {
                    "match_type": MatchType.STRUCTURAL_MATCH,
                    "score": 0.95,
                    "is_match": True,
                    "reason": f"Subdomain '{sub}' belongs to root domain '{dom}'",
                    "contradictions": []
                }

        # Fuzzy string similarity within same type (e.g. Person Name or Username)
        if type1 == type2:
            norm1 = self.normalize_string(val1)
            norm2 = self.normalize_string(val2)
            sim = self.jaro_winkler_similarity(norm1, norm2)
            
            # Check for property contradictions
            contradictions = []
            if props1 and props2:
                # Contradictory geolocations
                loc1 = props1.get("country") or props1.get("location")
                loc2 = props2.get("country") or props2.get("location")
                if loc1 and loc2 and loc1.lower() != loc2.lower():
                    contradictions.append(f"Geographic conflict: '{loc1}' vs '{loc2}'")

            if sim >= 0.85:
                return {
                    "match_type": MatchType.POSSIBLE_MATCH if not contradictions else MatchType.CONTRADICTORY,
                    "score": round(sim, 3),
                    "is_match": True if not contradictions else False,
                    "reason": f"High lexical similarity ({int(sim*100)}%) between '{val1}' and '{val2}'",
                    "contradictions": contradictions
                }

        return {
            "match_type": MatchType.POSSIBLE_MATCH,
            "score": 0.0,
            "is_match": False,
            "reason": "No structural or lexical correlation",
            "contradictions": []
        }

    def resolve_findings(self, findings: List[EvidenceFinding]) -> Dict[str, Any]:
        """
        Executes pairwise resolution across all findings to identify corroborated identities,
        duplicates, and contradictory assertions.
        """
        clusters: List[Dict[str, Any]] = []
        contradictions: List[Dict[str, Any]] = []

        seen_entities: Dict[str, EvidenceFinding] = {}
        for f in findings:
            key = f"{f.entity_type.value}:{f.entity_value.strip().lower()}"
            if key in seen_entities:
                existing = seen_entities[key]
                existing.confidence = ConfidenceLevel.CORROBORATED
            else:
                seen_entities[key] = f

        # Cross-comparison
        items = list(seen_entities.values())
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                res = self.compare_entities(
                    items[i].entity_value, items[i].entity_type,
                    items[j].entity_value, items[j].entity_type,
                    items[i].raw_payload, items[j].raw_payload
                )
                if res["is_match"] and res["score"] >= 0.85:
                    clusters.append({
                        "entity_a": items[i].entity_value,
                        "type_a": items[i].entity_type.value,
                        "entity_b": items[j].entity_value,
                        "type_b": items[j].entity_type.value,
                        "score": res["score"],
                        "match_type": res["match_type"].value,
                        "reason": res["reason"]
                    })
                if res["contradictions"]:
                    contradictions.append({
                        "entity_a": items[i].entity_value,
                        "entity_b": items[j].entity_value,
                        "conflicts": res["contradictions"]
                    })

        return {
            "unique_resolved_entities": len(seen_entities),
            "identity_clusters": clusters,
            "detected_contradictions": contradictions
        }

entity_resolution = EntityResolutionEngine()
