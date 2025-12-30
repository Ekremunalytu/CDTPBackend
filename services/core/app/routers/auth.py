from fastapi import APIRouter, HTTPException
from shared.database import db
from shared.models import UserLogin

router = APIRouter()

# ... imports
from datetime import timedelta, datetime
from jose import jwt
import os

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 days

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login")
@router.post("/auth/login")
async def login(user: UserLogin):
    # ... existing query ...
    query = "SELECT id, role FROM users WHERE username = $1 AND password_hash = $2 AND role = $3"
    result = await db.fetch_one(query, user.username, user.password, user.role.value)
    
    if result:
        user_data = dict(result)
        user_data['id'] = str(user_data['id'])
        
        # Hasta ise patient_id getir
        if user.role.value == 'PATIENT':
            patient_query = "SELECT id FROM patients WHERE user_id = $1"
            patient = await db.fetch_one(patient_query, result['id'])
            if patient:
                user_data['patient_id'] = str(patient['id'])
        
        # Bakıcı ise caregiver_id getir
        elif user.role.value == 'CAREGIVER':
            caregiver_query = "SELECT id FROM caregivers WHERE user_id = $1"
            caregiver = await db.fetch_one(caregiver_query, result['id'])
            if caregiver:
                user_data['caregiver_id'] = str(caregiver['id'])
        
        # Generate Token
        access_token = create_access_token(data={"sub": user.username, "role": user.role.value, "id": user_data['id']})
        
        # Build response with root-level IDs for frontend compatibility
        response = {
            "success": True, 
            "message": "Login successful", 
            "token": access_token,
            "access_token": access_token,  # For OAuth2 compatibility
            "user": user_data,
            "userId": user_data['id'],
            "role": user.role.value
        }
        
        # Add patient_id or caregiver_id at root level
        if 'patient_id' in user_data:
            response['patient_id'] = user_data['patient_id']
            response['patientId'] = user_data['patient_id']  # camelCase variant
        if 'caregiver_id' in user_data:
            response['caregiver_id'] = user_data['caregiver_id']
            response['caregiverId'] = user_data['caregiver_id']  # camelCase variant
        
        return response
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

