from pydantic import BaseModel
from typing import List, Dict

class RawSensorData(BaseModel):
    patient_id: str
    timestamp: float
    accelerometer: Dict[str, float]  # {"x": 0.1, "y": 0.2, "z": 9.8}
    gyroscope: Dict[str, float]      # {"x": 0.01, "y": 0.01, "z": 0.01}
    ppg_raw: List[int]               # [2048, 2050, ...]
