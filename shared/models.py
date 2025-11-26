from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserLogin(BaseModel):
    username: str
    password: str
    role: str

class MeasurementCreate(BaseModel):
    patient_id: str
    heart_rate: int
    inactivity_seconds: int

class EmergencyLog(BaseModel):
    id: int
    patient_id: str
    message: str
    is_resolved: bool
    created_at: datetime
