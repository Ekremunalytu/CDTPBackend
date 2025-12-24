from fastapi import APIRouter, HTTPException
from shared.database import db
from shared.models import MeasurementCreate
import socketio

router = APIRouter()

# SocketIO instance will be injected or imported. 
# For simplicity in this refactor, we will use a shared module or pass it.
# Better approach: Create a socket manager or import the 'sio' object from main (circular import risk)
# OR: Define sio in a separate file. Let's create app/socket_manager.py

from app.socket_manager import sio

@router.post("/measurements")
async def create_measurement(data: MeasurementCreate):
    from shared.measurement_service import MeasurementService
    
    # Ensure DB is connected
    if not db.pool:
         raise HTTPException(status_code=503, detail="Database not ready")

    service = MeasurementService(db.pool)
    
    try:
        # For manual measurements, we assume is_fall=False
        result = await service.process_measurement(
            data.patient_id, 
            data.heart_rate, 
            data.inactivity_seconds, 
            is_fall=False
        )
        return {"success": True, "status": result['status']}

    except Exception as e:
        print(f"Error in create_measurement: {e}")
        raise HTTPException(status_code=500, detail="Failed to record measurement")


