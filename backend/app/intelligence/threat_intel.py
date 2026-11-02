import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.evidence.models import EvidenceFinding, EntityType

logger = logging.getLogger("pravision.intelligence.threat_intel")

class ThreatIntelEngine:
    """
    Threat Intelligence Scoring and IOC Aggregation Engine:
    Combines telemetry from GreyNoise, AbuseIPDB, URLhaus, OpenSanctions, and HIBP
    to determine risk severity, adversary profiles, and compromise exposure.
    """

    def evaluate_threat_posture(self, findings: List[EvidenceFinding]) -> Dict[str, Any]:
        risk_score = 0
        indicators = []
        sanctions_matches = []
        known_malicious = False
        threat_actors = []

        for f in findings:
            src = f.source_name.lower()
            val = f.entity_value
            payload = f.raw_payload or {}

            # GreyNoise Check
            if "greynoise" in src:
                classification = payload.get("classification", "")
                actor = payload.get("actor")
                if classification == "malicious":
                    risk_score += 45
                    known_malicious = True
                    indicators.append({"type": "malicious_scanner", "detail": f"GreyNoise flagged scanner as malicious ({actor})"})
                elif classification == "benign":
                    indicators.append({"type": "benign_scanner", "detail": f"GreyNoise verified benign scanner ({actor})"})
                if actor and actor not in threat_actors:
                    threat_actors.append(actor)

            # AbuseIPDB Check
            elif "abuseipdb" in src:
                score = payload.get("abuseConfidenceScore", 0)
                if score > 0:
                    risk_score += min(40, int(score * 0.4))
                    indicators.append({"type": "abuse_reports", "detail": f"AbuseIPDB confidence score: {score}%"})

            # URLhaus Check
            elif "urlhaus" in src or "openosint" in src:
                url_cnt = payload.get("url_count", 0)
                if url_cnt > 0:
                    risk_score += 50
                    known_malicious = True
                    indicators.append({"type": "active_malware_distribution", "detail": f"Host associated with {url_cnt} malware delivery URLs"})

            # OpenSanctions Check
            elif "opensanctions" in src:
                score = payload.get("score", 0)
                datasets = payload.get("datasets", [])
                risk_score += 35
                sanctions_matches.append({
                    "entity": val,
                    "score": score,
                    "datasets": datasets
                })

            # Breach Exposure Check (HIBP / H8mail)
            elif "hibp" in src or "h8mail" in src:
                risk_score += 15
                indicators.append({"type": "credential_breach", "detail": f"Account or domain found in historical credential breaches"})

        # Cap score at 100
        risk_score = min(100, risk_score)

        if risk_score >= 75:
            severity = "CRITICAL"
        elif risk_score >= 50:
            severity = "HIGH"
        elif risk_score >= 25:
            severity = "MODERATE"
        elif risk_score > 0:
            severity = "LOW"
        else:
            severity = "BENIGN"

        return {
            "overall_risk_score": risk_score,
            "severity_level": severity,
            "is_known_malicious": known_malicious,
            "indicators": indicators,
            "sanctions_matches": sanctions_matches,
            "identified_actors": threat_actors,
            "assessment_timestamp": datetime.utcnow().isoformat()
        }

threat_intel_engine = ThreatIntelEngine()
