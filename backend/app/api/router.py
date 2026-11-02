import asyncio
import shutil
import uuid
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response

from app.engine.input_classifier import input_classifier, ClassifiedInput
from app.engine.investigation_orchestrator import orchestrator, ActiveInvestigation
from app.connectors.registry import connector_registry
from app.reports.report_generator import report_generator
from app.security import secret_vault
from app.config import settings
from app.privacy.privacy_controller import privacy_controller
from app.media_forensics.metadata_extractor import metadata_extractor, hash_calculator
from app.media_forensics.forensic_analyzer import forensic_analyzer

from app.storage.database import check_db_health
from app.storage.case_manager import case_manager
from app.storage.b2_storage import b2_storage
from app.storage.backup_system import backup_system, backup_scheduler
from app.intelligence.entity_resolution import entity_resolution
from app.intelligence.graph_analytics import graph_analytics
from app.intelligence.timeline_engine import timeline_engine
from app.intelligence.threat_intel import threat_intel_engine
from app.intelligence.document_intel import document_intel
from app.intelligence.ai_assistant import intelligence_assistant

router = APIRouter()

# ----------------- INPUT CLASSIFICATION -----------------

@router.post("/classify", response_model=ClassifiedInput)
async def classify_input(payload: Dict[str, str]):
    raw = payload.get("input", "")
    if not raw.strip():
        raise HTTPException(status_code=400, detail="Input cannot be empty.")
    return input_classifier.classify(raw)

# ----------------- INVESTIGATIONS -----------------

@router.post("/investigations")
async def create_investigation(payload: Dict[str, Any]):
    target = payload.get("target", "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="Target is required.")

    # Classify if mode or type not provided
    classification = input_classifier.classify(target)
    mode = payload.get("mode") or classification.mode
    depth = int(payload.get("depth", 2))

    inv = orchestrator.start_investigation(
        target_input=target,
        target_type=classification.detected_type,
        mode=mode,
        max_depth=depth
    )
    return inv

@router.get("/investigations/active")
async def get_active_investigation():
    inv = orchestrator.get_active()
    if not inv:
        return {"active": False, "investigation": None}
    return {"active": True, "investigation": inv}

@router.get("/investigations/{inv_id}")
async def get_investigation(inv_id: str):
    inv = orchestrator.get_active()
    if not inv or inv.id != inv_id:
        raise HTTPException(status_code=404, detail="Investigation not found in active memory.")
    return inv

@router.get("/investigations/{inv_id}/results")
async def get_investigation_results(inv_id: str):
    inv = orchestrator.get_active()
    if not inv or inv.id != inv_id:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return {
        "investigation_id": inv_id,
        "total_findings": len(orchestrator.get_findings()),
        "findings": orchestrator.get_findings()
    }

@router.get("/investigations/{inv_id}/graph")
async def get_investigation_graph(inv_id: str):
    inv = orchestrator.get_active()
    if not inv or inv.id != inv_id:
        raise HTTPException(status_code=404, detail="Investigation not found.")
    return orchestrator.get_graph()

@router.delete("/investigations/{inv_id}")
async def clear_investigation(inv_id: str):
    orchestrator.clear_investigation()
    return {"status": "cleared", "message": "Investigation wiped from volatile memory and ephemeral storage."}

@router.post("/investigations/{inv_id}/cancel")
async def cancel_investigation(inv_id: str):
    orchestrator.cancel_investigation()
    return {"status": "cancelled"}

# ----------------- WEBSOCKET LIVE STREAM -----------------

@router.websocket("/investigations/{inv_id}/live")
async def investigation_live_socket(websocket: WebSocket, inv_id: str):
    await websocket.accept()
    queue = asyncio.Queue()
    orchestrator.register_event_listener(queue)
    try:
        # Send initial state snapshot
        inv = orchestrator.get_active()
        if inv and inv.id == inv_id:
            await websocket.send_json({
                "type": "initial_state",
                "investigation": inv.dict(),
                "findings_count": len(orchestrator.get_findings()),
                "relationships_count": len(orchestrator.get_graph().edges)
            })

        while True:
            # Wait for internal event or client ping
            event = await queue.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        orchestrator.unregister_event_listener(queue)

# ----------------- CONNECTORS & TOOL CENTER -----------------

@router.get("/connectors")
async def list_connectors():
    return connector_registry.get_manifests()

@router.get("/connectors/{name}")
async def get_connector(name: str):
    c = connector_registry.get_connector(name)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found.")
    return c.get_manifest()

@router.post("/connectors/{name}/health-check")
async def run_connector_health(name: str):
    c = connector_registry.get_connector(name)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found.")
    status = await c.check_health()
    return {"name": name, "health": status, "manifest": c.get_manifest()}

@router.post("/connectors/{name}/toggle")
async def toggle_connector(name: str, payload: Dict[str, bool]):
    c = connector_registry.get_connector(name)
    if not c:
        raise HTTPException(status_code=404, detail="Connector not found.")
    enabled = payload.get("enabled", True)
    c.set_enabled(enabled)
    return {"name": name, "enabled": c.is_enabled, "manifest": c.get_manifest()}

# ----------------- MEDIA FORENSICS & UPLOAD -----------------

@router.post("/media/upload")
async def upload_media_file(file: UploadFile = File(...)):
    # Save to ephemeral memory-mapped temp dir
    safe_filename = f"{uuid.uuid4()}_{Path(file.filename).name}"
    content = await file.read()
    temp_path = privacy_controller.create_ephemeral_file(safe_filename, content)

    # Run EXIF and Hashes immediately
    meta = metadata_extractor.extract(str(temp_path))
    hashes = hash_calculator.calculate(str(temp_path))
    ela = forensic_analyzer.analyze_ela(str(temp_path))

    return {
        "filename": safe_filename,
        "original_name": file.filename,
        "file_path": str(temp_path),
        "metadata": meta,
        "hashes": hashes,
        "ela": ela
    }

# ----------------- REPORTS & EXPORTS -----------------

@router.post("/reports/export")
async def export_report(payload: Dict[str, str]):
    inv = orchestrator.get_active()
    if not inv:
        raise HTTPException(status_code=400, detail="No active investigation in memory to export.")

    format_type = payload.get("format", "html").lower()
    findings = orchestrator.get_findings()
    graph = orchestrator.get_graph().dict()

    if format_type == "json":
        json_str = report_generator.generate_json_report(inv, findings, graph)
        return Response(content=json_str, media_type="application/json", headers={"Content-Disposition": f"attachment; filename=pravision_dossier_{inv.id}.json"})

    elif format_type == "pdf":
        pdf_bytes = report_generator.generate_pdf_report(inv, findings)
        return Response(content=pdf_bytes, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=pravision_dossier_{inv.id}.pdf"})

    else: # HTML
        html_content = report_generator.generate_html_report(inv, findings, graph)
        return HTMLResponse(content=html_content, headers={"Content-Disposition": f"attachment; filename=pravision_dossier_{inv.id}.html"})

# ----------------- SETTINGS & SECRETS -----------------

@router.get("/settings")
async def get_settings():
    return {
        "app_name": settings.app_name,
        "full_name": settings.full_name,
        "tagline": settings.tagline,
        "version": settings.version,
        "limits": settings.limits.dict(),
        "configured_api_keys": secret_vault.get_status_overview(),
        "persist_history": settings.persist_investigations,
        "ephemeral_storage_path": str(settings.ephemeral_data_dir)
    }

@router.post("/settings")
async def update_settings(payload: Dict[str, Any]):
    # Update limits
    if "limits" in payload and isinstance(payload["limits"], dict):
        lim = payload["limits"]
        if "max_depth" in lim:
            settings.limits.max_depth = int(lim["max_depth"])
        if "max_discovered_entities" in lim:
            settings.limits.max_discovered_entities = int(lim["max_discovered_entities"])
        if "connector_timeout_seconds" in lim:
            settings.limits.connector_timeout_seconds = int(lim["connector_timeout_seconds"])

    # Update secrets securely in memory vault
    if "api_keys" in payload and isinstance(payload["api_keys"], dict):
        for k, v in payload["api_keys"].items():
            secret_vault.set_secret(k, v)

    return {"status": "updated", "configured_api_keys": secret_vault.get_status_overview()}

@router.post("/settings/purge")
async def purge_all_data():
    orchestrator.clear_investigation()
    count = privacy_controller.purge_all_ephemeral_data()
    return {"status": "purged", "items_removed": count}

# ----------------- CASES & DOSSIERS (STAGE 5) -----------------

@router.get("/cases")
async def list_cases(limit: int = 50, offset: int = 0):
    return await case_manager.list_cases(limit=limit, offset=offset)

@router.post("/cases")
async def create_case(payload: Dict[str, Any]):
    title = payload.get("title", "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Case title is required.")
    return await case_manager.create_case(
        title=title,
        description=payload.get("description"),
        created_by=payload.get("created_by", "Analyst"),
        classification=payload.get("classification", "UNCLASSIFIED"),
        tags=payload.get("tags", [])
    )

@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    case = await case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case

@router.delete("/cases/{case_id}")
async def delete_case(case_id: str):
    success = await case_manager.delete_case(case_id)
    if not success:
        raise HTTPException(status_code=404, detail="Case not found.")
    return {"status": "deleted", "case_id": case_id}

@router.post("/cases/{case_id}/save-active")
async def save_active_investigation_to_case(case_id: str):
    inv = orchestrator.get_active()
    if not inv:
        raise HTTPException(status_code=400, detail="No active investigation in memory to save.")
    findings = orchestrator.get_findings()
    graph = orchestrator.get_graph().dict()
    try:
        return await case_manager.save_investigation_to_case(
            case_id=case_id,
            investigation_id=inv.id,
            root_input=inv.root_input,
            root_type=inv.root_type.value if hasattr(inv.root_type, "value") else str(inv.root_type),
            mode=inv.mode,
            findings=findings,
            graph_nodes=graph.get("nodes", []),
            graph_edges=graph.get("edges", [])
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# ----------------- STORAGE & VAULT (STAGE 5) -----------------

@router.get("/storage/status")
async def get_storage_status():
    db_health = await check_db_health()
    b2_status = b2_storage.get_status()
    return {
        "database": db_health,
        "object_storage": b2_status
    }

@router.post("/storage/evidence/upload")
async def upload_evidence_to_vault(file: UploadFile = File(...), investigation_id: Optional[str] = Form(None)):
    data = await file.read()
    res = await b2_storage.upload_evidence(
        data=data,
        filename=file.filename or "evidence_file",
        content_type=file.content_type or "application/octet-stream",
        investigation_id=investigation_id
    )
    return res

@router.get("/storage/evidence/{file_key:path}")
async def download_evidence_from_vault(file_key: str):
    try:
        data, sha256_hash = await b2_storage.download_evidence(file_key)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f"attachment; filename={Path(file_key).name}",
                "X-Evidence-SHA256": sha256_hash
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Evidence file not found.")

# ----------------- AUTOMATED CASE DOSSIER BACKUPS (STAGE 5.5) -----------------

@router.get("/backup/status")
async def get_backup_status():
    return backup_scheduler.get_status()

@router.get("/backup/history")
async def get_backup_history():
    return backup_system.list_backups()

@router.post("/backup/run")
async def trigger_manual_backup(payload: Dict[str, Any] = None):
    case_id = payload.get("case_id") if payload else None
    sync_cloud = payload.get("sync_cloud", True) if payload else True
    try:
        res = await backup_system.create_backup(case_id=case_id, sync_to_cloud=sync_cloud)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup creation failed: {str(e)}")

@router.get("/backup/download/{backup_id}")
async def download_backup_package(backup_id: str):
    data = backup_system.get_backup_bytes(backup_id)
    if not data:
        raise HTTPException(status_code=404, detail="Backup archive not found.")
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename={backup_id}.pravision_bkp"
        }
    )

@router.post("/backup/restore")
async def restore_backup_package(
    file: UploadFile = File(...),
    verify_only: bool = Form(False),
    prefix: str = Form("")
):
    backup_bytes = await file.read()
    try:
        res = await backup_system.restore_backup(
            backup_bytes=backup_bytes,
            target_case_prefix=prefix,
            verify_only=verify_only
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Restoration failed: {str(e)}")

# ----------------- INTELLIGENCE WORKSTATION (STAGE 6) -----------------

@router.get("/intelligence/entity-resolution")
async def get_entity_resolution():
    findings = orchestrator.get_findings()
    return entity_resolution.resolve_findings(findings)

@router.get("/intelligence/graph-analytics")
async def get_graph_analytics():
    graph = orchestrator.get_graph().dict()
    return graph_analytics.analyze_graph(graph.get("nodes", []), graph.get("edges", []))

@router.get("/intelligence/shortest-path")
async def get_shortest_path(source: str, target: str):
    graph = orchestrator.get_graph().dict()
    path = graph_analytics.shortest_path(graph.get("nodes", []), graph.get("edges", []), source, target)
    if not path:
        return {"found": False, "path": []}
    return {"found": True, "path": path}

@router.get("/intelligence/timeline")
async def get_timeline():
    findings = orchestrator.get_findings()
    return timeline_engine.process_timeline(findings)

@router.get("/intelligence/threat-posture")
async def get_threat_posture():
    findings = orchestrator.get_findings()
    return threat_intel_engine.evaluate_threat_posture(findings)

@router.post("/intelligence/document/scan")
async def scan_document_text(payload: Dict[str, str]):
    text = payload.get("text", "")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty.")
    return document_intel.extract_entities_from_text(text)

@router.get("/intelligence/briefing")
async def get_ai_briefing():
    inv = orchestrator.get_active()
    if not inv:
        return {"error": "No active investigation in memory."}
    findings = orchestrator.get_findings()
    graph = orchestrator.get_graph().dict()
    threat = threat_intel_engine.evaluate_threat_posture(findings)
    return intelligence_assistant.generate_executive_briefing(
        target_input=inv.root_input,
        target_type=inv.root_type.value if hasattr(inv.root_type, "value") else str(inv.root_type),
        findings=findings,
        graph_data=graph,
        threat_posture=threat
    )

@router.post("/intelligence/ask")
async def ask_ai_assistant(payload: Dict[str, str]):
    query = payload.get("query", "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    inv = orchestrator.get_active()
    target_input = inv.root_input if inv else "Global Intelligence Scope"
    findings = orchestrator.get_findings()
    graph = orchestrator.get_graph().dict()
    return intelligence_assistant.answer_query(query, target_input, findings, graph)

@router.get("/intelligence/export/gexf")
async def export_gephi_gexf():
    inv = orchestrator.get_active()
    if not inv:
        raise HTTPException(status_code=400, detail="No active investigation in memory.")
    graph = orchestrator.get_graph().dict()
    gexf_content = graph_analytics.export_gexf(graph.get("nodes", []), graph.get("edges", []))
    return Response(
        content=gexf_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=pravision_{inv.id}.gexf"}
    )


