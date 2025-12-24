import socketio
import asyncpg
import os
import json
import asyncio

# Socket.IO Server - Management UI için
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins='*',  # Herhangi bir management client için
    ping_timeout=60,
    ping_interval=25
)

# Database Config
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cdtp_health")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def on_notification(conn, pid, channel, payload):
    """Callback for PostgreSQL LISTEN notifications"""
    try:
        data = json.loads(payload)
        print(f"Core received PostgreSQL notification on {channel}: {data}")
        
        if channel == "measurement_updates":
            await sio.emit('new_measurement', data)
        elif channel == "alert_updates":
            await sio.emit('alert', data)
    except Exception as e:
        print(f"Error handling notification: {e}")

async def pg_listener():
    """
    Background task to subscribe to PostgreSQL LISTEN channels and emit to Socket.IO
    """
    while True:
        try:
            conn = await asyncpg.connect(DATABASE_URL)
            print("Socket Manager: Connected to PostgreSQL")
            
            await conn.add_listener('measurement_updates', on_notification)
            await conn.add_listener('alert_updates', on_notification)
            
            print("Socket Manager: Subscribed to PostgreSQL channels")
            
            # Keep connection alive
            while True:
                await asyncio.sleep(60)
                
        except Exception as e:
            print(f"Socket Manager: Connection error - {e}, reconnecting in 5s...")
            await asyncio.sleep(5)

background_tasks = set()

async def start_background_tasks():
    print("Starting background tasks...")
    task = asyncio.create_task(pg_listener())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
