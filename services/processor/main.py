import asyncio
import redis.asyncio as redis
import json
import os
from datetime import datetime
from algorithms import detect_fall, calculate_bpm, check_inactivity
from database_writer import DatabaseWriter

# Redis Config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

async def process_data():
    print("Processor Service Starting...")
    
    # Initialize Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)
    
    # Initialize DB
    db_writer = DatabaseWriter()
    await db_writer.connect()
    
    print("Processor Service Ready. Waiting for data...")
    
    while True:
        try:
            # Blocking pop from Redis list 'sensor_data'
            # Returns tuple ('sensor_data', 'json_string')
            data = await r.blpop("sensor_data", timeout=0) 
            
            if data:
                raw_json = data[1]
                sensor_data = json.loads(raw_json)
                
                patient_id = sensor_data.get("patient_id")
                acc = sensor_data.get("accelerometer")
                ppg = sensor_data.get("ppg_raw")
                
                # 1. Run Algorithms
                is_fall = detect_fall(acc)
                bpm = calculate_bpm(ppg)
                # For MVP, we assume inactivity is 0 or calculated elsewhere, 
                # but let's use a placeholder or the simple check
                inactivity = 0 
                
                # 2. Determine Status
                status = "NORMAL"
                alert_msg = None
                
                if is_fall:
                    status = "CRITICAL"
                    alert_msg = "FALL DETECTED!"
                elif bpm < 40 or bpm > 120:
                    status = "WARNING"
                    alert_msg = f"Abnormal Heart Rate: {bpm} BPM"
                
                # 3. Save to DB
                await db_writer.save_measurement(patient_id, bpm, inactivity, status)
                
                # Publish Measurement Update
                measurement_data = {
                    "patient_id": patient_id,
                    "heart_rate": bpm,
                    "inactivity_seconds": inactivity,
                    "status": status,
                    "measured_at": datetime.now().isoformat()
                }
                await r.publish("measurement_updates", json.dumps(measurement_data))
                
                # 4. Create Alert if needed
                if alert_msg:
                    await db_writer.create_alert(patient_id, alert_msg)
                    
                    # Publish Alert Update
                    alert_data = {
                        "patient_id": patient_id,
                        "message": alert_msg,
                        "created_at": datetime.now().isoformat()
                    }
                    await r.publish("alert_updates", json.dumps(alert_data))
                    
        except Exception as e:
            print(f"Error processing data: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(process_data())
