from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from shared.database import db

router = APIRouter()


class SettingsUpdate(BaseModel):
    """Hasta ayarları güncelleme modeli"""
    bpm_lower_limit: Optional[int] = Field(None, ge=20, le=100, description="Minimum BPM eşiği")
    bpm_upper_limit: Optional[int] = Field(None, ge=60, le=250, description="Maksimum BPM eşiği")
    max_inactivity_seconds: Optional[int] = Field(None, ge=60, le=7200, description="Maksimum hareketsizlik süresi (saniye)")


class SettingsResponse(BaseModel):
    """Hasta ayarları yanıt modeli"""
    patient_id: str
    bpm_lower_limit: int
    bpm_upper_limit: int
    max_inactivity_seconds: int


@router.get("/settings/{patient_id}", response_model=SettingsResponse)
async def get_settings(patient_id: str):
    """
    Hasta ayarlarını getir.
    
    - **patient_id**: Hasta UUID'si
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


@router.put("/settings/{patient_id}", response_model=SettingsResponse)
async def update_settings(patient_id: str, settings: SettingsUpdate):
    """
    Hasta ayarlarını güncelle.
    
    - **patient_id**: Hasta UUID'si
    - **bpm_lower_limit**: Minimum BPM eşiği (20-100)
    - **bpm_upper_limit**: Maksimum BPM eşiği (60-250)
    - **max_inactivity_seconds**: Maksimum hareketsizlik süresi (60-7200 saniye)
    """
    # Build dynamic update query
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
    
    # Add patient_id and updated_at
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
