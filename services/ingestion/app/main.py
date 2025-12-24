from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from app.schemas import RawSensorData
import asyncpg
import json
import os

# Database Config
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cdtp_health")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

pool = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("Ingestion Service: Database connected")
    yield
    await pool.close()
    print("Ingestion Service: Database disconnected")

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"message": "Ingestion Service is Running"}

@app.post("/api/v1/ingest")
async def ingest_data(data: RawSensorData):
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO sensor_data_queue (patient_id, accelerometer, gyroscope, ppg_raw, timestamp)
                VALUES ($1, $2, $3, $4, $5)
            """, 
                data.patient_id, 
                json.dumps(data.accelerometer), 
                json.dumps(data.gyroscope), 
                data.ppg_raw, 
                data.timestamp
            )
        return {"success": True, "message": "Data queued"}
    except asyncpg.PostgresError as e:
        print(f"Database Error: {e}")
        raise HTTPException(status_code=503, detail="Service Unavailable (Database)")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
