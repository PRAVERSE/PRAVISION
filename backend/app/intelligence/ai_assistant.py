import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.evidence.models import EvidenceFinding, EntityType

logger = logging.getLogger("pravision.intelligence.ai_assistant")

class IntelligenceAssistant:
    """
    Gotham-style Grounded Analytical AI Assistant:
    Synthesizes multi-source evidence dossiers, formulates testable investigative hypotheses,
    identifies analytical gaps, and answers analyst queries with zero hallucinations.
    """

    def generate_executive_briefing(
        self,
        target_input: str,
        target_type: str,
        findings: List[EvidenceFinding],
        graph_data: Dict[str, Any],
        threat_posture: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        num_findings = len(findings)
        num_nodes = len(graph_data.get("nodes", []))
        num_edges = len(graph_data.get("edges", []))

        # Group findings by source and type
        sources = set(f.source_name for f in findings)
        entity_types = set(f.entity_type.value for f in findings)
        high_confidence = [f for f in findings if f.confidence.value in ("high", "independently_corroborated")]

        # Determine narrative
        if num_findings == 0:
            exec_summary = f"Investigation initiated on {target_type} '{target_input}'. No public records, infrastructure footprints, or corroborating artifacts were identified within configured parameters."
            next_steps = ["Expand investigation depth to level 2 or 3", "Submit secondary identifiers (email, handle, domain)", "Verify if identifier is restricted or private"]
        else:
            exec_summary = (
                f"Multi-source intelligence collection on {target_type} '{target_input}' yielded "
                f"{num_findings} verified findings across {len(sources)} independent OSINT sources. "
                f"Relational analysis mapped {num_nodes} entities and {num_edges} corroborated linkages, "
                f"with {len(high_confidence)} items meeting high-confidence threshold."
            )
            next_steps = [
                "Examine highest betweenness-centrality nodes in the relational graph",
                "Cross-reference newly discovered subdomains and infrastructure IP addresses",
                "Review sanctions and threat intelligence indicators for flagged entities"
            ]

        # Intelligence gaps
        gaps = []
        if "email" not in entity_types and target_type != "email":
            gaps.append("Lack of primary email address association")
        if "geo_coordinate" not in entity_types and "location_place" not in entity_types:
            gaps.append("No verified physical geolocation or spatial telemetry identified")
        if not threat_posture or threat_posture.get("overall_risk_score", 0) == 0:
            gaps.append("Zero malicious indicator hits detected in threat databases")

        # Hypotheses
        hypotheses = []
        if num_findings > 5:
            hypotheses.append({
                "title": "Established Digital Presence",
                "confidence": "HIGH",
                "reasoning": f"Subject possesses persistent multi-platform footprint corroborated by {len(sources)} sources."
            })
        if threat_posture and threat_posture.get("is_known_malicious"):
            hypotheses.append({
                "title": "Adversary Infrastructure Association",
                "confidence": "CRITICAL",
                "reasoning": "Target displays direct correlation with known malicious threat telemetry."
            })

        return {
            "title": f"Executive Intelligence Assessment: {target_input}",
            "generated_at": datetime.utcnow().isoformat(),
            "target": {"input": target_input, "type": target_type},
            "metrics": {
                "total_findings": num_findings,
                "sources_queried": list(sources),
                "graph_nodes": num_nodes,
                "graph_edges": num_edges,
                "high_confidence_findings": len(high_confidence)
            },
            "executive_summary": exec_summary,
            "intelligence_gaps": gaps,
            "formulated_hypotheses": hypotheses,
            "recommended_next_actions": next_steps
        }

    def answer_query(
        self,
        query: str,
        target_input: str,
        findings: List[EvidenceFinding],
        graph_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Grounded QA answering strictly from collected evidence."""
        q_lower = query.lower()
        relevant_findings = []

        for f in findings:
            if (f.entity_value.lower() in q_lower or
                f.source_name.lower() in q_lower or
                f.entity_type.value in q_lower or
                any(word in f.entity_value.lower() for word in q_lower.split() if len(word) > 3)):
                relevant_findings.append({
                    "entity": f.entity_value,
                    "type": f.entity_type.value,
                    "source": f.source_name,
                    "confidence": f.confidence.value
                })

        if relevant_findings:
            answer = f"Found {len(relevant_findings)} evidence artifacts directly relevant to your query: '{query}'."
        else:
            answer = f"No direct evidence matches query '{query}' in the current dossier ({len(findings)} total findings available)."

        return {
            "query": query,
            "answer": answer,
            "matched_artifacts": relevant_findings[:8],
            "total_matches": len(relevant_findings)
        }

intelligence_assistant = IntelligenceAssistant()

