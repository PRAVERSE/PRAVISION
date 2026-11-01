from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class ProvenanceRecord(BaseModel):
    finding_id: str
    discovered_by_connector: str
    parent_finding_id: Optional[str] = None
    source_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    method: str = "direct_query"

class ProvenanceTracker:
    """Tracks chain of custody and provenance history for every evidence finding."""

    def __init__(self):
        self._records: Dict[str, ProvenanceRecord] = {}

    def record(self, finding_id: str, connector_name: str, source_url: Optional[str] = None, parent_id: Optional[str] = None, method: str = "direct_query"):
        self._records[finding_id] = ProvenanceRecord(
            finding_id=finding_id,
            discovered_by_connector=connector_name,
            parent_finding_id=parent_id,
            source_url=source_url,
            method=method
        )

    def get_provenance(self, finding_id: str) -> Optional[ProvenanceRecord]:
        return self._records.get(finding_id)

    def clear(self):
        self._records.clear()
