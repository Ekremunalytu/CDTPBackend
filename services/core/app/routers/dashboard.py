from fastapi import APIRouter
from shared.database import db

router = APIRouter()

@router.get("/patients")
async def get_patients():
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
