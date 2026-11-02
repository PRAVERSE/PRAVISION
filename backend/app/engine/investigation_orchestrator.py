import asyncio
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from app.evidence.models import EvidenceFinding, EntityType, IntelligenceGraph
from app.connectors.base_connector import InvestigationRequest
from app.connectors.registry import connector_registry
from app.engine.discovery_queue import DiscoveryQueue, DiscoveryItem
from app.engine.depth_controller import DepthController
from app.engine.expansion_engine import expansion_engine
from app.engine.rate_limiter import rate_limiter
from app.engine.provenance_tracker import ProvenanceTracker
from app.evidence.source_deduplicator import source_deduplicator
from app.evidence.confidence_engine import confidence_engine
from app.graph.graph_engine import GraphEngine
from app.graph.relationship_mapper import relationship_mapper
from app.privacy.privacy_controller import privacy_controller

logger = logging.getLogger("pravision.orchestrator")

class ConnectorLiveStatus(BaseModel):
    name: str
    display_name: str
    status: str = "waiting" # waiting, running, completed, failed
    duration_ms: int = 0
    findings_count: int = 0
    error_message: Optional[str] = None

class ActiveInvestigation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    root_input: str
    root_type: EntityType
    mode: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "initialized" # initialized, running, completed, cancelled, error
    depth: int = 1
    total_findings: int = 0
    verified_relationships: int = 0
    connector_statuses: Dict[str, ConnectorLiveStatus] = Field(default_factory=dict)
    recent_events: List[Dict[str, Any]] = Field(default_factory=list)

class InvestigationOrchestrator:
    """
    Central recursive investigation coordinator:
    Executes relevant connectors, controls discovery depth, corroborates evidence,
    builds the relational graph, and maintains in-memory state.
    """

    def __init__(self):
        self._active_investigation: Optional[ActiveInvestigation] = None
        self._findings: List[EvidenceFinding] = []
        self._graph = GraphEngine()
        self._provenance = ProvenanceTracker()
        self._depth_controller = DepthController()
        self._discovery_queue = DiscoveryQueue()
        self._event_listeners: List[asyncio.Queue] = []
        self._current_task: Optional[asyncio.Task] = None
        self._is_cancelled: bool = False

    def get_active(self) -> Optional[ActiveInvestigation]:
        return self._active_investigation

    def get_findings(self) -> List[EvidenceFinding]:
        return self._findings

    def get_graph(self) -> IntelligenceGraph:
        return self._graph.get_graph()

    def register_event_listener(self, queue: asyncio.Queue):
        self._event_listeners.append(queue)

    def unregister_event_listener(self, queue: asyncio.Queue):
        if queue in self._event_listeners:
            self._event_listeners.remove(queue)

    async def emit_event(self, event_type: str, data: Dict[str, Any]):
        event = {
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        if self._active_investigation:
            self._active_investigation.recent_events.append(event)
            # Retain last 60 events in memory
            if len(self._active_investigation.recent_events) > 60:
                self._active_investigation.recent_events = self._active_investigation.recent_events[-60:]

        for queue in self._event_listeners:
            try:
                queue.put_nowait(event)
            except Exception:
                pass

    def start_investigation(self, target_input: str, target_type: EntityType, mode: str, max_depth: int = 2) -> ActiveInvestigation:
        # Clear existing investigation strictly from memory
        self.clear_investigation()

        inv = ActiveInvestigation(
            root_input=target_input,
            root_type=target_type,
            mode=mode,
            depth=max_depth
        )

        # Plan connectors
        candidate_connectors = connector_registry.get_connectors_for_entity(target_type)
        for c in candidate_connectors:
            inv.connector_statuses[c.name] = ConnectorLiveStatus(
                name=c.name,
                display_name=c.display_name,
                status="waiting"
            )

        self._active_investigation = inv
        self._depth_controller = DepthController(max_depth=max_depth)
        self._is_cancelled = False

        # Add root target to queue
        self._discovery_queue.push(DiscoveryItem(
            entity_value=target_input,
            entity_type=target_type,
            depth=1,
            discovered_by="root_submission"
        ))

        # Launch async execution loop
        self._current_task = asyncio.create_task(self._run_investigation_loop())
        return inv

    async def _run_investigation_loop(self):
        inv = self._active_investigation
        if not inv:
            return

        inv.status = "running"
        await self.emit_event("investigation_started", {"investigation_id": inv.id, "target": inv.root_input})

        try:
            while not self._discovery_queue.empty() and not self._is_cancelled:
                item = await self._discovery_queue.pop()

                if not self._depth_controller.can_expand(item.depth):
                    continue

                connectors = connector_registry.get_connectors_for_entity(item.entity_type)
                tasks = []
                for conn in connectors:
                    if self._is_cancelled:
                        break
                    tasks.append(self._execute_connector(conn, item))

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            inv.status = "completed" if not self._is_cancelled else "cancelled"
            await self.emit_event("investigation_finished", {"status": inv.status, "findings_count": len(self._findings)})

        except Exception as e:
            logger.error(f"Investigation execution error: {e}")
            inv.status = "error"
            await self.emit_event("investigation_error", {"error": str(e)})

    async def _execute_connector(self, conn, item: DiscoveryItem):
        inv = self._active_investigation
        if not inv or self._is_cancelled:
            return

        status_obj = inv.connector_statuses.get(conn.name)
        if not status_obj:
            status_obj = ConnectorLiveStatus(name=conn.name, display_name=conn.display_name)
            inv.connector_statuses[conn.name] = status_obj

        status_obj.status = "running"
        await self.emit_event("connector_started", {"connector": conn.name, "target": item.entity_value})

        start_time = time.time()
        req = InvestigationRequest(
            investigation_id=inv.id,
            target_value=item.entity_value,
            target_type=item.entity_type,
            mode=inv.mode,
            depth=item.depth
        )

        try:
            await rate_limiter.acquire(conn.name)
            findings = await conn.safe_execute(req)
            elapsed_ms = int((time.time() - start_time) * 1000)

            status_obj.duration_ms = elapsed_ms
            status_obj.status = "completed"
            status_obj.findings_count += len(findings)

            if findings:
                # Deduplicate and corroborate
                self._findings.extend(findings)
                self._findings = source_deduplicator.deduplicate(self._findings)
                self._findings = confidence_engine.evaluate_findings(self._findings)

                # Map to relational graph
                relationship_mapper.map_findings_to_graph(inv.root_input, inv.root_type, self._findings, self._graph)
                inv.total_findings = len(self._findings)
                inv.verified_relationships = len(self._graph.get_graph().edges)

                # Recursive expansion
                for finding in findings:
                    candidates = expansion_engine.extract_expansion_candidates(finding, item.depth)
                    for cand in candidates:
                        self._discovery_queue.push(cand)

                await self.emit_event("findings_updated", {
                    "connector": conn.name,
                    "new_findings": len(findings),
                    "total_findings": len(self._findings),
                    "relationships": inv.verified_relationships
                })

            await self.emit_event("connector_completed", {
                "connector": conn.name,
                "duration_ms": elapsed_ms,
                "findings": len(findings)
            })

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            status_obj.status = "failed"
            status_obj.duration_ms = elapsed_ms
            status_obj.error_message = str(e)
            await self.emit_event("connector_failed", {"connector": conn.name, "error": str(e)})

    def cancel_investigation(self):
        self._is_cancelled = True
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
        if self._active_investigation:
            self._active_investigation.status = "cancelled"

    def clear_investigation(self):
        """Zero persistent history enforcement: Wipes all memory, graph, queue, and scratch files."""
        self.cancel_investigation()
        self._active_investigation = None
        self._findings.clear()
        self._graph.clear()
        self._provenance.clear()
        self._discovery_queue.clear()
        self._depth_controller.reset()
        # Securely erase temporary media/documents
        privacy_controller.purge_all_ephemeral_data()

orchestrator = InvestigationOrchestrator()

