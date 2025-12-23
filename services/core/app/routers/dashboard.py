from fastapi import APIRouter
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

