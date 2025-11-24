from fastapi import APIRouter, HTTPException
from app.database import db
from app.models import MeasurementCreate
import socketio

router = APIRouter()

# SocketIO instance will be injected or imported. 
# For simplicity in this refactor, we will use a shared module or pass it.
# Better approach: Create a socket manager or import the 'sio' object from main (circular import risk)
# OR: Define sio in a separate file. Let's create app/socket_manager.py

from app.socket_manager import sio

@router.post("/measurements")
async def create_measurement(data: MeasurementCreate):
    try:
        # 1. Get Patient Settings
        settings_query = "SELECT * FROM patient_settings WHERE patient_id = $1"
        settings = await db.fetch_one(settings_query, data.patient_id)
        
        bpm_lower = settings['bpm_lower_limit'] if settings else 50
        bpm_upper = settings['bpm_upper_limit'] if settings else 120
        max_inactivity = settings['max_inactivity_seconds'] if settings else 900

        # 2. Determine Status
        status = 'NORMAL'
        alert_message = None

        if data.heart_rate < bpm_lower or data.heart_rate > bpm_upper:
            status = 'CRITICAL'
            alert_message = f"Abnormal Heart Rate: {data.heart_rate} BPM"
        elif data.inactivity_seconds > max_inactivity:
            status = 'WARNING'
            alert_message = f"High Inactivity: {data.inactivity_seconds}s"

        # 3. Save Measurement
        insert_query = """
            INSERT INTO measurements (patient_id, heart_rate, inactivity_seconds, status)
            VALUES ($1, $2, $3, $4)
            RETURNING measured_at
        """
        # We need measured_at for the socket event
        res = await db.fetch_one(insert_query, data.patient_id, data.heart_rate, data.inactivity_seconds, status)
        
        # Emit Real-time Data (Always)
        measurement_data = {
            "patient_id": data.patient_id,
            "heart_rate": data.heart_rate,
            "inactivity_seconds": data.inactivity_seconds,
            "status": status,
            "measured_at": res['measured_at'].isoformat() if res else None
        }
        await sio.emit('new_measurement', measurement_data)

        # 4. Create Alert if needed
        if status != 'NORMAL' and alert_message:
            alert_query = """
                INSERT INTO emergency_logs (patient_id, message)
                VALUES ($1, $2)
                RETURNING id, patient_id, message, created_at
            """
            alert = await db.fetch_one(alert_query, data.patient_id, alert_message)
            
            # Notify Caregivers (Alert only)
            if alert:
                alert_data = dict(alert)
                alert_data['created_at'] = alert_data['created_at'].isoformat()
                await sio.emit('alert', alert_data)

        return {"success": True, "status": status}

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to record measurement")
