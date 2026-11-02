from typing import List, Dict, Set
from urllib.parse import urlparse
from app.evidence.models import EvidenceFinding, ConfidenceLevel, MatchType

class ConfidenceEngine:
    """
    Evaluates evidence independence, corroboration, and assigns defensible confidence ratings.
    Ensures duplicate references from the same origin do not artificially inflate confidence.
    """

    @staticmethod
    def extract_source_domain(source_url: str | None) -> str:
        if not source_url:
            return "unknown_origin"
        try:
            parsed = urlparse(source_url)
            return parsed.netloc.lower() or "direct_api"
        except Exception:
            return "malformed_origin"

    def evaluate_findings(self, findings: List[EvidenceFinding]) -> List[EvidenceFinding]:
        """
        Groups findings by entity_type and entity_value, checks source independence,
        and recalculates confidence levels.
        """
        entity_groups: Dict[tuple, List[EvidenceFinding]] = {}
        for f in findings:
            key = (f.entity_type, f.entity_value.strip().lower())
            entity_groups.setdefault(key, []).append(f)

        for key, group in entity_groups.items():
            independent_sources: Set[str] = set()
            for f in group:
                origin = self.extract_source_domain(f.source_url) or f.source_name
                independent_sources.add(origin)

            source_count = len(independent_sources)

            for f in group:
                f.supporting_sources = list(independent_sources)
                if f.match_type == MatchType.EXACT_MATCH:
                    if source_count >= 3:
                        f.confidence = ConfidenceLevel.CORROBORATED
                        f.verification_status = "corroborated"
                    elif source_count == 2:
                        f.confidence = ConfidenceLevel.HIGH
                        f.verification_status = "verified_multi_source"
                    else:
                        f.confidence = ConfidenceLevel.MODERATE
                        f.verification_status = "single_verified_source"
                elif f.match_type == MatchType.POSSIBLE_MATCH:
                    if source_count >= 2:
                        f.confidence = ConfidenceLevel.MODERATE
                        f.verification_status = "multiple_candidates"
                    else:
                        f.confidence = ConfidenceLevel.LOW
                        f.verification_status = "unverified_candidate"
                elif f.match_type == MatchType.CONTRADICTORY:
                    f.confidence = ConfidenceLevel.LOW
                    f.verification_status = "disputed_evidence"
                else:
                    f.confidence = ConfidenceLevel.UNVERIFIED
                    f.verification_status = "preliminary"

        return findings

confidence_engine = ConfidenceEngine()

