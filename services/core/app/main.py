from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from shared.database import db
from app.socket_manager import sio, start_background_tasks
from app.routers import auth, measurements, dashboard, sos

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

# Include Routers
fastapi_app.include_router(auth.router, prefix="/api", tags=["Auth"])
fastapi_app.include_router(measurements.router, prefix="/api", tags=["Measurements"])
fastapi_app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])
fastapi_app.include_router(sos.router, prefix="/api", tags=["SOS"])

# Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
