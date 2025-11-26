import socketio
import redis.asyncio as redis
import os
import json
import asyncio

# Socket.IO Server
sio = socketio.AsyncServer(
    async_mode='asgi', 
    cors_allowed_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
    ping_timeout=60,
    ping_interval=25
)

# Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

async def redis_subscriber():
    """
    Background task to subscribe to Redis channels and emit to Socket.IO
    """
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("measurement_updates", "alert_updates")
    
    print("Socket Manager: Subscribed to Redis channels")

    async for message in pubsub.listen():
        if message['type'] == 'message':
            channel = message['channel']
            data = json.loads(message['data'])
            print(f"Core received Redis message on {channel}: {data}")
            
            if channel == "measurement_updates":
                await sio.emit('new_measurement', data)
            elif channel == "alert_updates":
                await sio.emit('alert', data)

background_tasks = set()

async def start_background_tasks():
    print("Starting background tasks...")
    task = asyncio.create_task(redis_subscriber())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
