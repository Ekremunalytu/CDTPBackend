"""
Processor Service

Sensör verilerini kuyruktan alır, algoritmaları çalıştırır ve sonuçları kaydeder.
"""
import asyncio
import asyncpg
import json
import os
from datetime import datetime, timezone
from algorithms import detect_fall, calculate_bpm, check_inactivity

# Database Config
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "cdtp_health")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


async def process_data(pool: asyncpg.Pool):
    """Ana veri işleme döngüsü. Pool dışarıdan geçilir."""
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
                        timestamp = row['timestamp']
                        
                        # Parse JSONB data (array format)
                        acc = json.loads(row['accelerometer']) if isinstance(row['accelerometer'], str) else row['accelerometer']
                        ppg = row['ppg_raw']
                        
                        # 2. Get previous state for inactivity calculation
                        last_movement_at_dt = await service.get_patient_state(patient_id, conn=conn)
                        last_movement_ts = last_movement_at_dt.timestamp() if last_movement_at_dt else None
                        
                        # 3. Run Algorithms (Updated for array format)
                        
                        # Düşme algılama (3-aşamalı)
                        is_fall, fall_type = detect_fall(acc)
                        if is_fall:
                            print(f"⚠️ DÜŞME TESPİT EDİLDİ! Hasta: {patient_id}, Tip: {fall_type}")
                        
                        # Kalp atışı hesaplama
                        bpm = calculate_bpm(ppg)
                        
                        # Hareketsizlik kontrolü
                        inactivity, is_moving = check_inactivity(
                            acc, 
                            timestamp, 
                            last_movement_ts
                        )
                        
                        # 4. Update State if moved
                        if is_moving:
                            await service.update_patient_state(
                                patient_id, 
                                datetime.fromtimestamp(timestamp, tz=timezone.utc), 
                                conn=conn
                            )
                        
                        # 5. Process Measurement (Evaluate -> Save -> Notify -> Alert)
                        result = await service.process_measurement(
                            patient_id, 
                            bpm, 
                            inactivity, 
                            is_fall,
                            conn=conn
                        )
                        
                        # 6. Mark as processed
                        await conn.execute(
                            "UPDATE sensor_data_queue SET processed = TRUE WHERE id = $1", 
                            row['id']
                        )
                            
                        status_emoji = "🟢" if result['status'] == "NORMAL" else "🟡" if result['status'] == "WARNING" else "🔴"
                        print(f"{status_emoji} Processed: {patient_id} | BPM: {bpm} | Status: {result['status']}")
                    else:
                        pass

            if not row:
                await asyncio.sleep(0.5)
                    
        except Exception as e:
            print(f"Error processing data: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(1)


async def check_inactivity_periodic(pool: asyncpg.Pool):
    """
    Periyodik hareketsizlik kontrolü.
    Her 30 saniyede bir tüm hastaları kontrol eder.
    """
    from shared.measurement_service import MeasurementService
    service = MeasurementService(pool)
    
    while True:
        try:
            await asyncio.sleep(30)  # 30 saniyede bir kontrol
            
            async with pool.acquire() as conn:
                # Aktif hastaların son hareket zamanlarını al
                rows = await conn.fetch("""
                    SELECT ps.patient_id, ps.last_movement_at, pset.max_inactivity_seconds
                    FROM patient_states ps
                    JOIN patient_settings pset ON ps.patient_id = pset.patient_id
                    WHERE ps.last_movement_at IS NOT NULL
                """)
                
                now = datetime.now(timezone.utc)
                
                for row in rows:
                    last_movement = row['last_movement_at']
                    max_inactivity = row['max_inactivity_seconds'] or 900
                    
                    if last_movement:
                        inactivity_seconds = (now - last_movement).total_seconds()
                        
                        if inactivity_seconds > max_inactivity:
                            # Hareketsizlik alarmı oluştur
                            patient_id = str(row['patient_id'])
                            print(f"⚠️ Hareketsizlik alarmı: {patient_id} - {int(inactivity_seconds)}s")
                            
                            # Alert oluştur (eğer son 5 dakikada zaten oluşturulmadıysa)
                            existing = await conn.fetchval("""
                                SELECT COUNT(*) FROM emergency_logs 
                                WHERE patient_id = $1 
                                AND message LIKE '%Hareketsizlik%'
                                AND created_at > NOW() - INTERVAL '5 minutes'
                            """, row['patient_id'])
                            
                            if existing == 0:
                                await service.process_measurement(
                                    patient_id,
                                    heart_rate=70,  # Normal varsayılan
                                    inactivity_seconds=int(inactivity_seconds),
                                    is_fall=False,
                                    conn=conn
                                )
                                
        except Exception as e:
            print(f"Inactivity check error: {e}")
            await asyncio.sleep(5)


async def main():
    print("Processor Service Starting...")
    pool = await asyncpg.create_pool(DATABASE_URL)
    print("Processor Service: Database connected")
    
    # Her iki task'ı da aynı pool ile çalıştır
    await asyncio.gather(
        process_data(pool),
        check_inactivity_periodic(pool)
    )


if __name__ == "__main__":
    asyncio.run(main())
