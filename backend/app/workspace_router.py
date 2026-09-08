"""
FastAPI router exposing the workspace-connect + real-codebase analysis endpoints.
"""
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.app import database
from backend.app.database import WorkspaceRecord
from backend.app import workspace as ws

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspace", tags=["workspace"])


class ConnectRequest(BaseModel):
    source: str          # 'github' | 'local'
    url: str = ""        # github URL when source == 'github'
    path: str = ""       # local path when source == 'local'


class AnalyzeRequest(BaseModel):
    workspace_id: str


def _get_ws(db, workspace_id: str) -> WorkspaceRecord:
    rec = db.query(WorkspaceRecord).filter(WorkspaceRecord.workspace_id == workspace_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' not found")
    return rec


def _rec_to_dict(rec: WorkspaceRecord) -> Dict[str, Any]:
    return {
        "workspace_id": rec.workspace_id,
        "name": rec.name,
        "source": rec.source,
        "url": rec.url or "",
        "root": rec.root,
        "branch": rec.branch or "",
        "connected_at": rec.connected_at.isoformat() if rec.connected_at else None,
        "last_analyzed_at": rec.last_analyzed_at.isoformat() if rec.last_analyzed_at else None,
        "metadata": rec.metadata_json or {},
    }


def _resolve_connected_paths() -> Set[str]:
    """Return all filesystem paths currently registered as workspaces."""
    paths: Set[str] = set()
    try:
        db = database.SessionLocal()
        try:
            for rec in db.query(WorkspaceRecord).all():
                paths.add(str(rec.root))
        finally:
            db.close()
    except Exception:
        pass
    return paths


def is_path_already_connected(path: str) -> bool:
    """True if the given path (or its parent) is already a connected workspace."""
    import os
    norm = os.path.normpath(os.path.abspath(path)).lower()
    for p in _resolve_connected_paths():
        np = os.path.normpath(p).lower()
        if np == norm or norm.startswith(np + os.sep) or np.startswith(norm + os.sep):
            return True
    return False


@router.get("/list")
def list_workspaces():
    db = database.SessionLocal()
    try:
        recs = db.query(WorkspaceRecord).order_by(WorkspaceRecord.connected_at.desc()).all()
        return {"workspaces": [_rec_to_dict(r) for r in recs]}
    finally:
        db.close()


@router.post("/connect")
def connect_workspace(req: ConnectRequest):
    if req.source not in ("github", "local"):
        raise HTTPException(status_code=400, detail="source must be 'github' or 'local'")

    try:
        conn = ws.connect_workspace(req.source, url=req.url, path=req.path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("workspace connect failed")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

    # Guard against overlapping local paths
    if conn["source"] == "local" and is_path_already_connected(conn["root"]):
        raise HTTPException(
            status_code=409,
            detail=f"Path '{conn['root']}' is already connected as a workspace.",
        )

    db = database.SessionLocal()
    try:
        rec = WorkspaceRecord(
            workspace_id=conn["id"],
            name=conn["name"],
            source=conn["source"],
            url=conn.get("url") or None,
            root=conn["root"],
            branch=conn.get("branch") or None,
        )
        db.add(rec)
        db.commit()
        return _rec_to_dict(rec)
    finally:
        db.close()


@router.post("/analyze")
def analyze_workspace(req: AnalyzeRequest):
    db = database.SessionLocal()
    try:
        rec = _get_ws(db, req.workspace_id)
        try:
            analysis = ws.analyze_workspace(rec.root)
        except Exception as e:
            logger.exception("analyze failed")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

        rec.metadata_json = analysis.get("metadata", {})
        rec.last_analyzed_at = datetime.utcnow()
        db.commit()
        return {"workspace_id": rec.workspace_id, **analysis}
    finally:
        db.close()


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str):
    db = database.SessionLocal()
    try:
        rec = _get_ws(db, workspace_id)
        return _rec_to_dict(rec)
    finally:
        db.close()


@router.delete("/{workspace_id}")
def delete_workspace(workspace_id: str):
    db = database.SessionLocal()
    try:
        rec = _get_ws(db, workspace_id)
        db.delete(rec)
        db.commit()
        return {"ok": True, "workspace_id": workspace_id}
    finally:
        db.close()
