import logging
import asyncio
import json
from typing import Dict, List, Any
from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.config import settings
from backend.app import database
from backend.app.database import init_db, IncidentRecord
from backend.app.simulator import router as simulator_router, sim_state
from backend.app.agent import agent_app
from backend.app.memory import search_past_incidents, save_to_incident_memory
from backend.app.workspace_router import router as workspace_router
from backend.app.live_investigation_router import router as live_router

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="RootCause AI API", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

# Mount simulator endpoints
app.include_router(simulator_router)
app.include_router(workspace_router)
app.include_router(live_router)

# --- WEBSOCKET BROADCAST MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, incident_id: str, websocket: WebSocket):
        await websocket.accept()
        if incident_id not in self.active_connections:
            self.active_connections[incident_id] = []
        self.active_connections[incident_id].append(websocket)
        logger.info(f"WebSocket client connected to incident: {incident_id}")

    def disconnect(self, incident_id: str, websocket: WebSocket):
        if incident_id in self.active_connections:
            if websocket in self.active_connections[incident_id]:
                self.active_connections[incident_id].remove(websocket)
        logger.info(f"WebSocket client disconnected from incident: {incident_id}")

    async def broadcast(self, incident_id: str, state: Dict[str, Any]):
        if incident_id in self.active_connections:
            # We must serialize properly
            payload = json.loads(json.dumps(state, default=str))
            for connection in self.active_connections[incident_id]:
                try:
                    await connection.send_json(payload)
                except Exception as e:
                    logger.warning(f"Error sending websocket payload: {e}")

manager = ConnectionManager()

# --- BACKEND API ROUTES ---
api_router = APIRouter(prefix="/api")

class InvestigateRequest(BaseModel):
    incident_id: str
    incident_type: str
    severity: str
    symptoms: Dict[str, Any]

async def execute_graph_loop(incident_id: str, initial_state: Dict[str, Any]):
    """
    Background worker that runs the LangGraph state machine node-by-node and broadcasts updates.
    """
    logger.info(f"Starting background LangGraph execution for incident {incident_id}...")
    
    # Store initial state
    db = database.SessionLocal()
    try:
        # Check if record exists
        record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
        if not record:
            record = IncidentRecord(
                incident_id=incident_id,
                incident_type=initial_state["incident_type"],
                status="TRIAGED",
                state_json=initial_state
            )
            db.add(record)
            db.commit()
    except Exception as e:
        logger.error(f"Failed to create incident database record: {e}")
    finally:
        db.close()

    # Define input state
    state = {
        "incident_id": incident_id,
        "incident_type": initial_state["incident_type"],
        "severity": initial_state["severity"],
        "symptoms": initial_state["symptoms"],
        "timeline": [],
        "observations": [],
        "evidence": [],
        "hypotheses": [],
        "experiments": [],
        "experiment_results": [],
        "belief_scores": {},
        "candidate_root_causes": [],
        "confirmed_root_cause": None,
        "confidence": 0.0,
        "actions_taken": [],
        "failed_actions": [],
        "next_action": None,
        "human_approval_required": False,
        "investigation_status": "TRIAGING",
        "logs": ["Ingested incident alert into LangGraph workflow."]
    }

    # Broadcast start state
    await manager.broadcast(incident_id, state)
    await asyncio.sleep(1.0) # Visual delay for demo

    config = {"configurable": {"thread_id": incident_id}}
    
    try:
        # Run graph step by step
        async for event in agent_app.astream(state, config, stream_mode="values"):
            # Update state with current graph value
            state = event
            
            # Update DB
            db = database.SessionLocal()
            try:
                record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
                if record:
                    record.state_json = state
                    record.status = state["investigation_status"]
                    db.commit()
            except Exception as e:
                logger.error(f"Failed to update db record: {e}")
            finally:
                db.close()
                
            # Broadcast state
            await manager.broadcast(incident_id, state)
            await asyncio.sleep(1.5) # Simulating execution intervals for UI readability

    except Exception as e:
        logger.error(f"LangGraph execution error: {e}")
        state["investigation_status"] = "FAILED"
        state["logs"].append(f"Fatal error during agent run: {str(e)}")
        
        # Save error state
        db = database.SessionLocal()
        try:
            record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
            if record:
                record.state_json = state
                record.status = "FAILED"
                db.commit()
        except:
            pass
        finally:
            db.close()
            
        await manager.broadcast(incident_id, state)

@api_router.post("/investigate")
def investigate(request: InvestigateRequest, background_tasks: BackgroundTasks):
    # Ensure simulator active faults match the triaged type (sync faults to support demo flow)
    # If the user starts an investigation, let's sync the simulator's active faults if none are set
    if not sim_state.active_faults:
        if "preprocessing" in request.incident_type.lower() or request.incident_id == "104":
            sim_state.preprocessing_mode = "standard_scaler"
            sim_state.latency_injection = 2.2
            sim_state.active_faults = ["preprocessing_mismatch"]

    initial_state = request.dict()
    
    # Spawn graph execution loop
    background_tasks.add_task(execute_graph_loop, request.incident_id, initial_state)
    
    return {"status": "started", "incident_id": request.incident_id}

@api_router.get("/incidents")
def list_incidents():
    db = database.SessionLocal()
    try:
        records = db.query(IncidentRecord).all()
        return [{
            "incident_id": r.incident_id,
            "incident_type": r.incident_type,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat()
        } for r in records]
    finally:
        db.close()

@api_router.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    db = database.SessionLocal()
    try:
        record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        return record.state_json
    finally:
        db.close()

@api_router.post("/incidents/{incident_id}/approve")
async def approve_incident(incident_id: str, background_tasks: BackgroundTasks):
    """
    Operator approves the proposed fix patch.
    This resumes the LangGraph workflow starting at 'verify_fix'.
    """
    db = database.SessionLocal()
    state = None
    try:
        record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        state = record.state_json
    finally:
        db.close()

    if state["investigation_status"] != "AWAITING_APPROVAL":
        raise HTTPException(status_code=400, detail="Incident is not awaiting approval")

    # Update state: reset human gate and trigger fix phase
    state["human_approval_required"] = False
    state["investigation_status"] = "VERIFYING"
    state["logs"].append("Operator approved proposed patch. Applying hotfix inside production sandbox...")

    # Spawn background task to run the verify_fix node and finish
    background_tasks.add_task(resume_verification_loop, incident_id, state)

    return {"status": "approved"}

async def resume_verification_loop(incident_id: str, state: Dict[str, Any]):
    # Broadcast status change
    await manager.broadcast(incident_id, state)
    await asyncio.sleep(1.0)
    
    # Import verification node directly to process state
    from backend.app.agent import verify_fix_node
    
    try:
        # Run verification step
        node_result = verify_fix_node(state)
        updated_state = {**state, **node_result}
        
        # If fix succeeded, also apply to simulated production (out of sandbox) to resolve incident!
        if updated_state["investigation_status"] == "RESOLVED":
            sim_state.reset() # clear faults in simulated API
            
            # Save to long term memory
            save_to_incident_memory(
                symptoms_text=f"Model accuracy dropped from 94.2% to 71.3% after DEP-401 deployment. Preprocessing scaled values out of bounds.",
                root_cause="Standard Scaler preprocessing normalization applied without model tuning.",
                evidence_chain={
                    "git_commit": "8f31a2c",
                    "sandbox_test": "PREPROCESSING_MISMATCH: TRUE"
                },
                fix_diff="Revert preprocessing.py normalization back to MinMax scaling",
                verification_metrics={"before_accuracy": 0.713, "after_accuracy": 0.939}
            )
            
        # Update DB
        db = database.SessionLocal()
        try:
            record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
            if record:
                record.state_json = updated_state
                record.status = updated_state["investigation_status"]
                db.commit()
        except:
            pass
        finally:
            db.close()
            
        # Broadcast final state
        await manager.broadcast(incident_id, updated_state)
        
    except Exception as e:
        logger.error(f"Failed to resume verification loop: {e}")

@api_router.get("/memory/search")
def search_memory(query: str):
    return search_past_incidents(query)

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

# Mount NeoGuard documents folder for dashboard download
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Try to find the documents directory relative to the project root
_base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.app.config import settings as _settings
DOCUMENTS_DIR = os.path.join(_settings.target_app_dir, "static", "documents")
if os.path.exists(DOCUMENTS_DIR):
    app.mount("/api/documents", StaticFiles(directory=DOCUMENTS_DIR), name="documents")
    logger.info(f"Successfully mounted NeoGuard static documents at /api/documents")
else:
    logger.warning(f"NeoGuard static documents folder not found at {DOCUMENTS_DIR}")

# Serve built frontend for production deployment
FRONTEND_DIST = os.path.join(_base_dir, "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="frontend-assets")
    
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
    
    logger.info(f"Frontend static files served from {FRONTEND_DIST}")
else:
    logger.info("No frontend dist found. Running in API-only mode.")


# --- WEBSOCKET STREAMING ---
@app.websocket("/ws/incidents/{incident_id}")
async def websocket_endpoint(websocket: WebSocket, incident_id: str):
    await manager.connect(incident_id, websocket)
    
    # Send current state immediately if it exists
    db = database.SessionLocal()
    try:
        record = db.query(IncidentRecord).filter(IncidentRecord.incident_id == incident_id).first()
        if record:
            await websocket.send_json(record.state_json)
    except Exception as e:
        logger.warning(f"Failed to send initial websocket status: {e}")
    finally:
        db.close()
        
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(incident_id, websocket)
    except Exception as e:
        logger.warning(f"WebSocket execution error: {e}")
        manager.disconnect(incident_id, websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
