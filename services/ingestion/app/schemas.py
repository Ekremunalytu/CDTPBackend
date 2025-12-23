from pydantic import BaseModel, Field
from typing import List, Dict
from uuid import UUID

class RawSensorData(BaseModel):
    """
    Mobil uygulamadan gelen sensör verisi.
    ESP32'den gelen ham veri mobil uygulamada işlenir ve bu formatta backend'e gönderilir.
    """
    patient_id: str  # UUID formatında string olarak gelir
    timestamp: float
    # Array format: Mobil uygulama bir zaman penceresi içindeki değerleri toplar
    accelerometer: Dict[str, List[float]]  # {"x": [0.1, 0.2, ...], "y": [...], "z": [...]}
    gyroscope: Dict[str, List[float]]      # {"x": [...], "y": [...], "z": [...]}
    ppg_raw: List[int]                     # [2048, 2050, ...]
