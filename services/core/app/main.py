from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
import os
import json
from typing import Dict, Set
from shared.database import db
from app.socket_manager import sio, start_background_tasks, set_vitals_connections
from app.routers import auth, measurements, sos, settings
from app.routers import dashboard as dashboard_router
from app.routers import patients as patients_router
from app.routers import caregivers as caregivers_router
from app.routers import sensor as sensor_router

# WebSocket connection managers (defined early for socket_manager access)
vitals_connections: Dict[str, Set[WebSocket]] = {}  # patient_id -> connected caregivers
patient_connections: Dict[str, WebSocket] = {}  # patient_id -> patient websocket

# FastAPI App
fastapi_app = FastAPI()

# CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO - Wrap FastAPI app
socket_app = socketio.ASGIApp(sio, fastapi_app)

# vitals_connections is now defined at the top of the file

# Database Events
@fastapi_app.on_event("startup")
async def startup():
    await db.connect()
    await start_background_tasks()
    # Share vitals_connections with socket_manager for WebSocket broadcasting
    set_vitals_connections(vitals_connections)

@fastapi_app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

@fastapi_app.get("/health")
async def health():
    """Health check endpoint for Docker"""
    return {"status": "healthy"}

# Static Files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    fastapi_app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Dashboard Route
@fastapi_app.get("/dashboard")
async def dashboard():
    """Serve the web dashboard"""
    dashboard_path = os.path.join(static_dir, "dashboard.html")
    if os.path.exists(dashboard_path):
        return FileResponse(dashboard_path)
    return {"message": "Dashboard not found"}

# Include Routers
fastapi_app.include_router(auth.router, prefix="/api", tags=["Auth"])
fastapi_app.include_router(measurements.router, prefix="/api", tags=["Measurements"])
fastapi_app.include_router(dashboard_router.router, prefix="/api", tags=["Dashboard"])
fastapi_app.include_router(sos.router, prefix="/api", tags=["SOS"])
fastapi_app.include_router(settings.router, prefix="/api", tags=["Settings"])
fastapi_app.include_router(patients_router.router, prefix="/api", tags=["Patients"])
fastapi_app.include_router(caregivers_router.router, prefix="/api", tags=["Caregivers"])
fastapi_app.include_router(sensor_router.router, prefix="/api", tags=["Sensor"])

# Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

# ============ WEBSOCKET ENDPOINTS (Android Native) ============
import asyncio


@fastapi_app.websocket("/ws/vitals/{patient_id}")
async def websocket_vitals(websocket: WebSocket, patient_id: str):
    """
    Bakıcılar bu endpoint'e bağlanarak hasta vital verilerini dinler.
    Socket.IO'dan gelen events bu bağlantılara forward edilir.
    """
    await websocket.accept()
    
    # Add to connections
    if patient_id not in vitals_connections:
        vitals_connections[patient_id] = set()
    vitals_connections[patient_id].add(websocket)
    
    print(f"Caregiver connected to vitals for patient: {patient_id}")
    
    try:
        while True:
            # Keep connection alive, wait for close
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_text(json.dumps({"type": "ack", "data": data}))
    except WebSocketDisconnect:
        vitals_connections[patient_id].discard(websocket)
        print(f"Caregiver disconnected from vitals for patient: {patient_id}")


@fastapi_app.websocket("/ws/patient/{patient_id}")
async def websocket_patient(websocket: WebSocket, patient_id: str):
    """
    Hastalar bu endpoint'e bağlanarak vital verilerini gönderir.
    Gelen veriler bakıcılara broadcast edilir.
    """
    await websocket.accept()
    patient_connections[patient_id] = websocket
    
    print(f"Patient connected: {patient_id}")
    
    try:
        while True:
            data = await websocket.receive_text()
            parsed = json.loads(data)
            
            # Broadcast to caregivers watching this patient
            if patient_id in vitals_connections:
                for caregiver_ws in vitals_connections[patient_id].copy():
                    try:
                        await caregiver_ws.send_text(json.dumps({
                            "type": "vital_data",
                            "patient_id": patient_id,
                            "data": parsed
                        }))
                    except Exception:
                        vitals_connections[patient_id].discard(caregiver_ws)
            
            # Also emit via Socket.IO for web clients
            await sio.emit('vital_data', {
                "patient_id": patient_id,
                "data": parsed
            })
            
            await websocket.send_text(json.dumps({"type": "ack", "received": True}))
    except WebSocketDisconnect:
        if patient_id in patient_connections:
            del patient_connections[patient_id]
        print(f"Patient disconnected: {patient_id}")
