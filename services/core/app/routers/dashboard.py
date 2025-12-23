from fastapi import APIRouter, HTTPException
from shared.database import db

router = APIRouter()

@router.get("/patients")
async def get_patients(caregiver_id: str = None):
    if caregiver_id:
        query = """
            SELECT p.id, p.name, u.username 
            FROM patients p
            JOIN users u ON p.user_id = u.id
            JOIN patient_caregiver pc ON p.id = pc.patient_id
            WHERE pc.caregiver_id = $1
        """
        rows = await db.fetch_all(query, caregiver_id)
    else:
        # Fallback for Admin or debugging: list all
        query = """
            SELECT p.id, p.name, u.username 
            FROM patients p
            JOIN users u ON p.user_id = u.id
        """
        rows = await db.fetch_all(query)
    
    return [dict(row) for row in rows]

@router.get("/alerts")
async def get_alerts():
    query = """
        SELECT e.id, e.message, e.created_at, p.name as patient_name 
        FROM emergency_logs e
        JOIN patients p ON e.patient_id = p.id
        ORDER BY e.created_at DESC
        LIMIT 50
    """
    rows = await db.fetch_all(query)
    return [dict(row) for row in rows]

from shared.models import PatientSettingsUpdate

@router.put("/patients/{patient_id}/settings")
async def update_settings(patient_id: str, settings: PatientSettingsUpdate):
    # 1. Check if settings record exists, if not create (though trigger handles creation)
    # 2. Update fields
    fields = []
    values = []
    idx = 1
    
    if settings.bpm_lower_limit is not None:
        fields.append(f"bpm_lower_limit = ${idx}")
        values.append(settings.bpm_lower_limit)
        idx += 1
    if settings.bpm_upper_limit is not None:
        fields.append(f"bpm_upper_limit = ${idx}")
        values.append(settings.bpm_upper_limit)
        idx += 1
    if settings.max_inactivity_seconds is not None:
        fields.append(f"max_inactivity_seconds = ${idx}")
        values.append(settings.max_inactivity_seconds)
        idx += 1
        
    if not fields:
        return {"success": True, "message": "No changes requested"}
        
    values.append(patient_id)
    query = f"UPDATE patient_settings SET {', '.join(fields)} WHERE patient_id = ${idx}"
    
    await db.execute(query, *values)
    return {"success": True, "message": "Settings updated"}


# ============ YENİ ENDPOINT'LER ============

@router.get("/patients/{patient_id}/measurements/latest")
async def get_latest_measurements(patient_id: str, limit: int = 10):
    """Hastanın son N ölçümünü getirir."""
    query = """
        SELECT id, heart_rate, inactivity_seconds, status, measured_at
        FROM measurements
        WHERE patient_id = $1
        ORDER BY measured_at DESC
        LIMIT $2
    """
    rows = await db.fetch_all(query, patient_id, limit)
    result = []
    for row in rows:
        item = dict(row)
        item['measured_at'] = item['measured_at'].isoformat()
        result.append(item)
    return result


@router.get("/patients/{patient_id}/settings")
async def get_patient_settings(patient_id: str):
    """Hastanın mevcut ayarlarını getirir."""
    query = """
        SELECT bpm_lower_limit, bpm_upper_limit, max_inactivity_seconds, updated_at
        FROM patient_settings
        WHERE patient_id = $1
    """
    row = await db.fetch_one(query, patient_id)
    if row:
        result = dict(row)
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
        return result
    else:
        raise HTTPException(status_code=404, detail="Patient settings not found")


@router.get("/patients/{patient_id}/status")
async def get_patient_status(patient_id: str):
    """Hastanın anlık durumunu getirir (son ölçüm + son alert)."""
    # Son ölçüm
    measurement_query = """
        SELECT heart_rate, inactivity_seconds, status, measured_at
        FROM measurements
        WHERE patient_id = $1
        ORDER BY measured_at DESC
        LIMIT 1
    """
    measurement = await db.fetch_one(measurement_query, patient_id)
    
    # Son çözülmemiş alert
    alert_query = """
        SELECT id, message, created_at
        FROM emergency_logs
        WHERE patient_id = $1 AND is_resolved = FALSE
        ORDER BY created_at DESC
        LIMIT 1
    """
    alert = await db.fetch_one(alert_query, patient_id)
    
    result = {
        "patient_id": patient_id,
        "last_measurement": None,
        "active_alert": None
    }
    
    if measurement:
        m = dict(measurement)
        m['measured_at'] = m['measured_at'].isoformat()
        result['last_measurement'] = m
    
    if alert:
        a = dict(alert)
        a['created_at'] = a['created_at'].isoformat()
        result['active_alert'] = a
    
    return result
