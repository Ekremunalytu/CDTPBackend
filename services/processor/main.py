import asyncio
import asyncpg
import json
import os
from datetime import datetime
from algorithms import detect_fall, calculate_bpm, check_inactivity
from database_writer import DatabaseWriter

# Database Config
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cdtp_health")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def process_data():
    print("Processor Service Starting...")
    
    # Initialize DB Pool
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("Processor Service: Database connected")
    
    # Initialize Services
    # Remove separate database_writer usage in favor of MeasurementService
    from shared.measurement_service import MeasurementService
    service = MeasurementService(pool)
    
    print("Processor Service Ready. Waiting for data...")
    
    while True:
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # 1. Fetch next unprocessed item safely
                    row = await conn.fetchrow("""
                        SELECT * FROM sensor_data_queue 
                        WHERE processed = FALSE 
                        ORDER BY created_at 
                        LIMIT 1 
                        FOR UPDATE SKIP LOCKED
                    """)
                
                    if row:
                        patient_id = row['patient_id']
                        # Handle JSONB or JSON string parsing
                        acc = json.loads(row['accelerometer']) if isinstance(row['accelerometer'], str) else row['accelerometer']
                        ppg = row['ppg_raw']
                        timestamp = row['timestamp']
                        
                        
                        # 2. Get previous state for inactivity calculation (Use SAME connection)
                        last_movement_at_dt = await service.get_patient_state(patient_id, conn=conn)
                        last_movement_ts = last_movement_at_dt.timestamp() if last_movement_at_dt else None
                        
                        # 3. Run Algorithms
                        is_fall = detect_fall(acc)
                        bpm = calculate_bpm(ppg)
                        
                        # Calculate Inactivity
                        inactivity = check_inactivity(acc, timestamp, timestamp, last_movement_ts)
                        
                        # Update State if moved
                        # If inactivity is 0, it means the user moved (based on check_inactivity logic)
                        if inactivity == 0:
                            # Update state to NOW (or timestamp of packet)
                            await service.update_patient_state(patient_id, datetime.fromtimestamp(timestamp), conn=conn)
                        
                        # 4. Process Measurement (Evaluate -> Save -> Notify -> Alert)
                        result = await service.process_measurement(
                            patient_id, 
                            bpm, 
                            inactivity, 
                            is_fall,
                            conn=conn
                        )
                        
                        # 5. Mark as processed (Commit happens on exit)
                        await conn.execute("UPDATE sensor_data_queue SET processed = TRUE WHERE id = $1", row['id'])
                            
                        print(f"Processed measurement for {patient_id}: {result['status']}")
                    else:
                        # No data, wait outside transaction? 
                        # Actually asyncpg transaction block exit commits.
                        pass

            if not row:
                # Sleep if we didn't find anything
                await asyncio.sleep(0.5)
                    
        except Exception as e:
            print(f"Error processing data: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(process_data())

