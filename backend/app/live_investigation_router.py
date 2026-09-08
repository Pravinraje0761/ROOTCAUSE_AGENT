"""
FastAPI router for the live-repo investigation subsystem.

POST /api/live/investigate   - start a live investigation (background)
GET  /api/live/list          - list all live incidents for a workspace
GET  /api/live/{incident_id} - get current state of a live investigation
POST /api/live/{incident_id}/retry - retry from next hypothesis
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from backend.app import database
from backend.app.database import WorkspaceRecord, LiveIncidentRecord
from backend.app.workspace import understand_project, analyze_workspace
from backend.app.live_investigation import run_live_investigation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/live", tags=["live-investigation"])

# In-memory progress store for investigations still running.
# On restart, in-progress investigations are not resumed (SQLite limitation).
_progress: Dict[str, Dict[str, Any]] = {}


class InvestigateRequest(BaseModel):
    workspace_id: str
    symptom: str
    endpoint: str = ""
    metrics_file: str = ""
    test_command: str = ""


def _rec_to_dict(rec: LiveIncidentRecord) -> Dict[str, Any]:
    return {
        "incident_id": rec.incident_id,
        "workspace_id": rec.workspace_id,
        "symptom": rec.symptom,
        "config": rec.config_json or {},
        "status": rec.status,
        "understanding": rec.understanding_json or {},
        "hypotheses": rec.hypotheses_json or [],
        "iteration_results": rec.iteration_results_json or [],
        "root_cause": rec.root_cause_json,
        "health_before": rec.health_before_json or {},
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


def _workspace_root(ws_id: str) -> str:
    db = database.SessionLocal()
    try:
        rec = db.query(WorkspaceRecord).filter(WorkspaceRecord.workspace_id == ws_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail=f"Workspace '{ws_id}' not found")
        return rec.root
    finally:
        db.close()


def _save_progress(incident_id: str, update: Dict[str, Any]):
    """Merge progress update into in-memory store."""
    if incident_id not in _progress:
        _progress[incident_id] = {"steps": []}
    _progress[incident_id].update(update)
    _progress[incident_id]["steps"].append(update.get("last_step", ""))


def _run_in_background(incident_id: str, root: str, symptom: str, config: Dict[str, Any]):
    """Run the full investigation in a background thread and persist the result."""
    def _cb(entry):
        _save_progress(incident_id, {"last_step": entry.get("step", ""), "last_message": entry.get("message", "")})

    try:
        result = run_live_investigation(
            workspace_id=incident_id,
            root=root,
            symptom=symptom,
            config=config,
            progress_cb=_cb,
        )
        db = database.SessionLocal()
        try:
            rec = db.query(LiveIncidentRecord).filter(LiveIncidentRecord.incident_id == incident_id).first()
            if rec:
                rec.status = result.get("final_status", "UNRESOLVED")
                rec.understanding_json = result.get("understanding", {})
                rec.hypotheses_json = result.get("hypotheses", [])
                rec.iteration_results_json = result.get("iteration_results", [])
                rec.root_cause_json = result.get("root_cause")
                rec.health_before_json = result.get("health_before", {})
                rec.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
        _save_progress(incident_id, {"last_step": "done", "result": result})
    except Exception as e:
        logger.exception("Live investigation failed")
        _save_progress(incident_id, {"last_step": "error", "error": str(e)})
        db = database.SessionLocal()
        try:
            rec = db.query(LiveIncidentRecord).filter(LiveIncidentRecord.incident_id == incident_id).first()
            if rec:
                rec.status = "UNRESOLVED"
                rec.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()


@router.post("/investigate")
def start_investigation(req: InvestigateRequest, background: BackgroundTasks):
    root = _workspace_root(req.workspace_id)
    import uuid
    inc_id = f"LIVE-{uuid.uuid4().hex[:8]}"
    config = {
        "endpoint": req.endpoint,
        "metrics_file": req.metrics_file,
        "test_command": req.test_command or "",
    }
    db = database.SessionLocal()
    try:
        rec = LiveIncidentRecord(
            incident_id=inc_id,
            workspace_id=req.workspace_id,
            symptom=req.symptom,
            config_json=config,
            status="INVESTIGATING",
        )
        db.add(rec)
        db.commit()
    finally:
        db.close()

    background.add_task(_run_in_background, inc_id, root, req.symptom, config)
    return {"incident_id": inc_id, "status": "INVESTIGATING"}


@router.get("/list")
def list_live_incidents(workspace_id: Optional[str] = None):
    db = database.SessionLocal()
    try:
        q = db.query(LiveIncidentRecord).order_by(LiveIncidentRecord.created_at.desc())
        if workspace_id:
            q = q.filter(LiveIncidentRecord.workspace_id == workspace_id)
        recs = q.limit(50).all()
        return {"incidents": [_rec_to_dict(r) for r in recs]}
    finally:
        db.close()


@router.get("/{incident_id}")
def get_live_incident(incident_id: str):
    db = database.SessionLocal()
    try:
        rec = db.query(LiveIncidentRecord).filter(LiveIncidentRecord.incident_id == incident_id).first()
        if not rec:
            raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found")
        data = _rec_to_dict(rec)
        # Attach in-progress steps if still running
        if incident_id in _progress:
            data["live_progress"] = _progress[incident_id]
        return data
    finally:
        db.close()
