from fastapi import APIRouter, HTTPException
from app.database import db
from app.models import UserLogin

router = APIRouter()

@router.post("/login")
async def login(user: UserLogin):
    query = "SELECT id, role FROM users WHERE username = $1 AND password_hash = $2 AND role = $3"
    result = await db.fetch_one(query, user.username, user.password, user.role)
    
    if result:
        user_data = dict(result)
        # If user is a patient, fetch patient_id
        if user.role == 'PATIENT':
            patient_query = "SELECT id FROM patients WHERE user_id = $1"
            patient = await db.fetch_one(patient_query, user_data['id'])
            if patient:
                user_data['patient_id'] = str(patient['id'])
        
        return {"success": True, "user": user_data}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")
