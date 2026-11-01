import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
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
