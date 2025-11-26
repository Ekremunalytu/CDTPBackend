from fastapi import FastAPI, HTTPException
from app.schemas import RawSensorData
import redis
import json
import os

app = FastAPI()

# Redis Connection
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
r = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)

@app.get("/")
async def root():
    return {"message": "Ingestion Service is Running"}

@app.post("/api/v1/ingest")
async def ingest_data(data: RawSensorData):
    try:
        # Push data to Redis list 'sensor_data'
        # We store it as a JSON string
        r.rpush("sensor_data", data.model_dump_json())
        return {"success": True, "message": "Data queued"}
    except redis.RedisError as e:
        print(f"Redis Error: {e}")
        raise HTTPException(status_code=503, detail="Service Unavailable (Redis)")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
