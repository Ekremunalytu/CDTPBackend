from pydantic import BaseModel, field_validator

from typing import Optional
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    PATIENT = "PATIENT"
    CAREGIVER = "CAREGIVER"
    ADMIN = "ADMIN"

class UserLogin(BaseModel):
    username: str
    password: str
    role: UserRole

    @field_validator('role', mode='before')
    @classmethod
    def case_insensitive_role(cls, v):
        if isinstance(v, str):
            return v.upper()
        return v

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

class PatientSettingsUpdate(BaseModel):
    bpm_lower_limit: Optional[int] = None
    bpm_upper_limit: Optional[int] = None
    max_inactivity_seconds: Optional[int] = None

