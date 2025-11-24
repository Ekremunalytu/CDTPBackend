from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
from app.database import db
from app.socket_manager import sio
from app.routers import auth, measurements, dashboard

# FastAPI App
app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Socket.IO
socket_app = socketio.ASGIApp(sio, app)

# Database Events
@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.disconnect()

# Include Routers
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(measurements.router, prefix="/api", tags=["Measurements"])
app.include_router(dashboard.router, prefix="/api", tags=["Dashboard"])

# Socket.IO Events
@sio.event
async def connect(sid, environ):
    print(f"Client connected: {sid}")

@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")
