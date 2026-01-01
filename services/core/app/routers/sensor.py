"""
Sensor & ECG Router

Raw sensör verisi ve ECG segmentlerini işleyen endpoint'ler.
Android uygulaması ile uyumlu API.
"""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from shared.database import db
import json

router = APIRouter()


class SensorDataCreate(BaseModel):
    """Raw sensör verisi modeli"""
    patient_id: str
    timestamp: float
    accelerometer: Dict[str, List[float]]
    gyroscope: Dict[str, List[float]]
    ppg_raw: List[int]


class ECGSegmentCreate(BaseModel):
    """ECG segment verisi modeli"""
    patient_id: str
    sample_rate: int = 250
    started_at: str  # ISO format datetime
    duration_ms: int
    samples: List[int]


@router.post("/sensor-data")
async def create_sensor_data(data: SensorDataCreate):
    """
    Raw sensör verisini sensor_data_queue tablosuna kaydeder.
    Ingestion servisi gibi çalışır.
    
    Request Body:
        - patient_id: Hasta UUID
        - timestamp: Unix timestamp
        - accelerometer: {"x": [...], "y": [...], "z": [...]}
        - gyroscope: {"x": [...], "y": [...], "z": [...]}
        - ppg_raw: PPG değerleri array
    """
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        query = """
            INSERT INTO sensor_data_queue (patient_id, accelerometer, gyroscope, ppg_raw, timestamp)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id
        """
        result = await db.fetch_one(
            query,
            data.patient_id,
            json.dumps(data.accelerometer),
            json.dumps(data.gyroscope),
            data.ppg_raw,
            data.timestamp
        )
        
        return {"success": True, "message": "Sensor data queued", "id": result['id'] if result else None}
    except Exception as e:
        print(f"Sensor data error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to queue sensor data: {str(e)}")


@router.post("/ecg-segments")
async def create_ecg_segment(data: ECGSegmentCreate):
    """
    ECG segment verisini kaydeder.
    
    Request Body:
        - patient_id: Hasta UUID
        - sample_rate: Örnekleme hızı (default 250 Hz)
        - started_at: Başlangıç zamanı (ISO format)
        - duration_ms: Süre (ms)
        - samples: ECG değerleri array
    """
    if not db.pool:
        raise HTTPException(status_code=503, detail="Database not ready")
    
    try:
        query = """
            INSERT INTO ecg_segments (patient_id, sample_rate, started_at, duration_ms, samples)
            VALUES ($1, $2, $3::timestamptz, $4, $5)
            RETURNING id
        """
        result = await db.fetch_one(
            query,
            data.patient_id,
            data.sample_rate,
            data.started_at,
            data.duration_ms,
            data.samples
        )
        
        return {"success": True, "message": "ECG segment saved", "id": result['id'] if result else None}
    except Exception as e:
        print(f"ECG segment error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save ECG segment: {str(e)}")


@router.get("/live-heart-rates")
async def get_live_heart_rates(
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    Canlı nabız verilerini v_live_heart_rates view'dan getirir.
    
    Args:
        limit: Maksimum kayıt sayısı
    
    Returns:
        List of heart rate records with:
        - id: Ölçüm ID
        - patient_name: Hasta adı
        - heart_rate: Nabız
        - status: NORMAL/WARNING/CRITICAL
        - measured_at: Ölçüm zamanı
    """
    query = """
        SELECT id, patient_name, heart_rate, status, measured_at
        FROM v_live_heart_rates
        LIMIT $1
    """
    rows = await db.fetch_all(query, limit)
    
    result = []
    for row in rows:
        item = dict(row)
        item['measured_at'] = item['measured_at'].isoformat() if item.get('measured_at') else None
        result.append(item)
    
    return result
