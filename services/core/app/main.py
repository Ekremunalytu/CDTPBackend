from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import socketio
import os
from shared.database import db
from app.socket_manager import sio, start_background_tasks
from app.routers import auth, measurements, sos, settings
from app.routers import dashboard as dashboard_router

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

# Database Events
@fastapi_app.on_event("startup")
async def startup():
    await db.connect()
    await start_background_tasks()

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

# Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
