import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.evidence.models import EvidenceFinding

logger = logging.getLogger("pravision.intelligence.timeline")

class TimelineEngine:
    """
    Constructs normalized chronological event sequences from multi-source OSINT evidence,
    detects temporal activity bursts, and maps infrastructure and identity progression.
    """

    def process_timeline(self, findings: List[EvidenceFinding]) -> Dict[str, Any]:
        events: List[Dict[str, Any]] = []

        for f in findings:
            payload = f.raw_payload or {}
            
            # 1. Check for specific event timestamps in payload
            event_time = (
                payload.get("not_before") or
                payload.get("created_at") or
                payload.get("firstseen") or
                payload.get("seendate") or
                payload.get("capture_time")
            )

            # Fallback to collection timestamp
            dt = None
            if event_time:
                try:
                    if isinstance(event_time, str):
                        # Simple ISO parser
                        dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
                except Exception:
                    dt = None

            if not dt:
                dt = f.collection_timestamp or datetime.utcnow()

            events.append({
                "id": f.id,
                "timestamp": dt.isoformat(),
                "event_type": f.entity_type.value,
                "entity_value": f.entity_value,
                "source": f.source_name,
                "confidence": f.confidence.value,
                "summary": f"{f.source_name} observed {f.entity_type.value}: {f.entity_value}",
                "raw_metadata": payload
            })

        # Sort chronologically
        events.sort(key=lambda x: x["timestamp"])

        # Burst Detection: identify time windows with unusual density
        bursts = self._detect_bursts(events)

        return {
            "total_events": len(events),
            "earliest_event": events[0]["timestamp"] if events else None,
            "latest_event": events[-1]["timestamp"] if events else None,
            "events": events,
            "detected_bursts": bursts
        }

    def _detect_bursts(self, events: List[Dict[str, Any]], window_hours: int = 24, min_density: int = 4) -> List[Dict[str, Any]]:
        if len(events) < min_density:
            return []

        bursts = []
        for i in range(len(events)):
            try:
                t_start = datetime.fromisoformat(events[i]["timestamp"])
            except Exception:
                continue

            window_events = [events[i]]
            for j in range(i + 1, len(events)):
                try:
                    t_curr = datetime.fromisoformat(events[j]["timestamp"])
                    if t_curr - t_start <= timedelta(hours=window_hours):
                        window_events.append(events[j])
                    else:
                        break
                except Exception:
                    continue

            if len(window_events) >= min_density:
                bursts.append({
                    "start_time": t_start.isoformat(),
                    "event_count": len(window_events),
                    "description": f"Concentrated activity cluster ({len(window_events)} events within {window_hours}h)"
                })
        return bursts[:5]

timeline_engine = TimelineEngine()
