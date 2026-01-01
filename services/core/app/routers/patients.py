"""
Patients Router

Hasta bilgileri, ölçümler ve acil durum loglarını getiren endpoint'ler.
Android uygulaması ile uyumlu API.
"""
from fastapi import APIRouter, HTTPException, Query
from shared.database import db

router = APIRouter()


@router.get("/patients/{patient_id}")
async def get_patient(patient_id: str):
    """
    Tek hasta detay bilgisini getirir.
    
    Returns:
        - id: Hasta UUID
        - name: Hasta adı
        - birth_date: Doğum tarihi
        - medical_info: Tıbbi bilgiler
        - user_id: Bağlı kullanıcı ID
    """
    query = """
        SELECT p.id, p.user_id, p.name, p.birth_date, p.medical_info, p.created_at
        FROM patients p
        WHERE p.id = $1
    """
    row = await db.fetch_one(query, patient_id)
    
    if row:
        result = dict(row)
        result['id'] = str(result['id'])
        result['user_id'] = str(result['user_id']) if result.get('user_id') else None
        result['birth_date'] = result['birth_date'].isoformat() if result.get('birth_date') else None
        result['created_at'] = result['created_at'].isoformat() if result.get('created_at') else None
        return result
    else:
        raise HTTPException(status_code=404, detail="Patient not found")


@router.get("/patients/{patient_id}/measurements")
async def get_patient_measurements(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Hasta ölçümlerini sayfalama destekli olarak getirir.
    
    Args:
        patient_id: Hasta UUID
        limit: Sayfa başına kayıt (max 100)
        offset: Atlama miktarı
    
    Returns:
        List of measurements with:
        - id: Ölçüm ID
        - heart_rate: Nabız
        - inactivity_seconds: Hareketsizlik süresi
        - status: NORMAL/WARNING/CRITICAL
        - measured_at: Ölçüm zamanı
    """
    query = """
        SELECT id, heart_rate, inactivity_seconds, status, measured_at
        FROM measurements
        WHERE patient_id = $1
        ORDER BY measured_at DESC
        LIMIT $2 OFFSET $3
    """
    rows = await db.fetch_all(query, patient_id, limit, offset)
    
    result = []
    for row in rows:
        item = dict(row)
        item['measured_at'] = item['measured_at'].isoformat() if item.get('measured_at') else None
        result.append(item)
    
    return result


@router.get("/patients/{patient_id}/emergency-logs")
async def get_patient_emergency_logs(
    patient_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):
    """
    Hasta acil durum geçmişini getirir.
    
    Args:
        patient_id: Hasta UUID
        limit: Sayfa başına kayıt (max 100)
        offset: Atlama miktarı
    
    Returns:
        List of emergency logs with:
        - id: Log ID
        - message: Acil durum mesajı
        - is_resolved: Çözüldü mü
        - created_at: Oluşturulma zamanı
    """
    query = """
        SELECT id, message, is_resolved, created_at
        FROM emergency_logs
        WHERE patient_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
    """
    rows = await db.fetch_all(query, patient_id, limit, offset)
    
    result = []
    for row in rows:
        item = dict(row)
        item['created_at'] = item['created_at'].isoformat() if item.get('created_at') else None
        result.append(item)
    
    return result


# ============ PATIENT SETTINGS ============
# Mobil app uyumlu endpoint'ler: /api/patients/{id}/settings

from pydantic import BaseModel, Field
from typing import Optional


class PatientSettingsUpdate(BaseModel):
    """Hasta ayarları güncelleme modeli"""
    bpm_lower_limit: Optional[int] = Field(None, ge=20, le=100)
    bpm_upper_limit: Optional[int] = Field(None, ge=60, le=250)
    max_inactivity_seconds: Optional[int] = Field(None, ge=60, le=7200)


@router.get("/patients/{patient_id}/settings")
async def get_patient_settings(patient_id: str):
    """
    Hasta ayarlarını getir.
    
    Returns:
        - patient_id: Hasta UUID
        - bpm_lower_limit: Minimum BPM eşiği
        - bpm_upper_limit: Maksimum BPM eşiği
        - max_inactivity_seconds: Hareketsizlik limiti (saniye)
    """
    query = "SELECT * FROM patient_settings WHERE patient_id = $1"
    row = await db.fetch_one(query, patient_id)
    
    if not row:
        raise HTTPException(status_code=404, detail="Patient settings not found")
    
    return {
        "patient_id": str(row["patient_id"]),
        "bpm_lower_limit": row["bpm_lower_limit"],
        "bpm_upper_limit": row["bpm_upper_limit"],
        "max_inactivity_seconds": row["max_inactivity_seconds"]
    }


@router.put("/patients/{patient_id}/settings")
async def update_patient_settings(patient_id: str, settings: PatientSettingsUpdate):
    """
    Hasta ayarlarını güncelle.
    
    Args:
        patient_id: Hasta UUID
        settings: Güncellenecek ayarlar
    
    Returns:
        Güncellenmiş ayarlar
    """
    updates = []
    values = []
    idx = 1
    
    if settings.bpm_lower_limit is not None:
        updates.append(f"bpm_lower_limit = ${idx}")
        values.append(settings.bpm_lower_limit)
        idx += 1
    
    if settings.bpm_upper_limit is not None:
        updates.append(f"bpm_upper_limit = ${idx}")
        values.append(settings.bpm_upper_limit)
        idx += 1
    
    if settings.max_inactivity_seconds is not None:
        updates.append(f"max_inactivity_seconds = ${idx}")
        values.append(settings.max_inactivity_seconds)
        idx += 1
    
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    values.append(patient_id)
    query = f"""
        UPDATE patient_settings 
        SET {', '.join(updates)}, updated_at = NOW()
        WHERE patient_id = ${idx}
        RETURNING patient_id, bpm_lower_limit, bpm_upper_limit, max_inactivity_seconds
    """
    
    row = await db.fetch_one(query, *values)
    
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return {
        "patient_id": str(row["patient_id"]),
        "bpm_lower_limit": row["bpm_lower_limit"],
        "bpm_upper_limit": row["bpm_upper_limit"],
        "max_inactivity_seconds": row["max_inactivity_seconds"]
    }

