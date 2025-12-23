from fastapi import APIRouter, HTTPException
from shared.database import db
from shared.models import UserLogin

router = APIRouter()

@router.post("/login")
async def login(user: UserLogin):
    """
    Basit login endpoint'i.
    Başarılı girişte kullanıcı bilgilerini ve role göre patient_id veya caregiver_id döner.
    """
    query = "SELECT id, role FROM users WHERE username = $1 AND password_hash = $2 AND role = $3"
    result = await db.fetch_one(query, user.username, user.password, user.role)
    
    if result:
        user_data = dict(result)
        user_data['id'] = str(user_data['id'])
        
        # Hasta ise patient_id getir
        if user.role == 'PATIENT':
            patient_query = "SELECT id FROM patients WHERE user_id = $1"
            patient = await db.fetch_one(patient_query, result['id'])
            if patient:
                user_data['patient_id'] = str(patient['id'])
        
        # Bakıcı ise caregiver_id getir
        elif user.role == 'CAREGIVER':
            caregiver_query = "SELECT id FROM caregivers WHERE user_id = $1"
            caregiver = await db.fetch_one(caregiver_query, result['id'])
            if caregiver:
                user_data['caregiver_id'] = str(caregiver['id'])
        
        return {"success": True, "user": user_data}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

