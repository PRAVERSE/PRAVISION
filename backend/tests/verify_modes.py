import asyncio
from app.engine.investigation_orchestrator import orchestrator
from app.engine.input_classifier import InvestigationMode
from app.evidence.models import EntityType

async def run_and_wait(target: str, target_type: EntityType, mode: str, max_depth: int = 1, timeout: float = 30.0):
    print(f"\n==========================================")
    print(f"Starting: {target} ({target_type.value}, mode={mode})")
    inv = orchestrator.start_investigation(
        target_input=target,
        target_type=target_type,
        mode=mode,
        max_depth=max_depth
    )
    start_time = asyncio.get_event_loop().time()
    while inv.status in ("initialized", "running"):
        await asyncio.sleep(0.5)
        if asyncio.get_event_loop().time() - start_time > timeout:
            print(f"Timed out after {timeout}s")
            break
    
    findings = orchestrator.get_findings()
    graph = orchestrator.get_graph()
    print(f"Result Status: {inv.status}")
    print(f"Total Findings: {len(findings)}, Graph Nodes: {len(graph.nodes)}, Graph Edges: {len(graph.edges)}")
    for name, st in inv.connector_statuses.items():
        if st.status != "waiting":
            print(f"  [{st.status.upper()}] {name} ({st.duration_ms}ms) -> {st.findings_count} findings {('(' + st.error_message + ')') if st.error_message else ''}")
    return inv, findings

async def main():
    # 1. Mode 4: Phone
    await run_and_wait("+14155552671", EntityType.PHONE, InvestigationMode.PHONE, max_depth=1)

    # 2. Mode 5: Website / Domain
    await run_and_wait("example.com", EntityType.DOMAIN, InvestigationMode.WEBSITE_DOMAIN, max_depth=1)

if __name__ == "__main__":
    asyncio.run(main())
