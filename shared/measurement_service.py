import json
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import asyncpg
from shared.business_logic import evaluate_measurement

class MeasurementService:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def process_measurement(
        self, 
        patient_id: str, 
        heart_rate: int, 
        inactivity_seconds: int, 
        is_fall: bool = False,
        conn: asyncpg.Connection = None
    ) -> Dict[str, Any]:
        """
        Full pipeline: Get settings -> Evaluate -> Save -> Alert -> Notify
        Returns the processed measurement data including status.
        """
        if conn:
            return await self._execute_pipeline(conn, patient_id, heart_rate, inactivity_seconds, is_fall)
        else:
            async with self.pool.acquire() as new_conn:
                return await self._execute_pipeline(new_conn, patient_id, heart_rate, inactivity_seconds, is_fall)

    async def _execute_pipeline(self, conn, patient_id, heart_rate, inactivity_seconds, is_fall):
        # 1. Get Settings
        settings = await self._get_settings(conn, patient_id)
        
        # 2. Evaluate
        status, alert_msg = evaluate_measurement(
            heart_rate, 
            inactivity_seconds, 
            settings, 
            is_fall
        )
        
        # 3. Save Measurement
        measured_at = await self._save_measurement(conn, patient_id, heart_rate, inactivity_seconds, status)
        
        result = {
            "patient_id": str(patient_id),
            "heart_rate": heart_rate,
            "inactivity_seconds": inactivity_seconds,
            "status": status,
            "measured_at": measured_at.isoformat()
        }
        
        # 4. Notify (Real-time update)
        await conn.execute(
            "SELECT pg_notify('measurement_updates', $1)", 
            json.dumps(result)
        )
        
        # 5. Handle Alert
        if alert_msg:
            await self._create_alert(conn, patient_id, alert_msg)
            
        return result

    async def update_patient_state(self, patient_id: str, last_movement_at: datetime, conn: asyncpg.Connection = None):
        """Updates the last movement timestamp for inactivity tracking."""
        query = """
            INSERT INTO patient_states (patient_id, last_movement_at, updated_at)
            VALUES ($1, $2, NOW())
            ON CONFLICT (patient_id) 
            DO UPDATE SET last_movement_at = EXCLUDED.last_movement_at, updated_at = NOW()
        """
        if conn:
             await conn.execute(query, patient_id, last_movement_at)
        else:
             async with self.pool.acquire() as new_conn:
                 await new_conn.execute(query, patient_id, last_movement_at)

    async def get_patient_state(self, patient_id: str, conn: asyncpg.Connection = None) -> Optional[datetime]:
        """Returns the last_movement_at timestamp."""
        query = "SELECT last_movement_at FROM patient_states WHERE patient_id = $1"
        if conn:
            return await conn.fetchval(query, patient_id)
        else:
            async with self.pool.acquire() as new_conn:
                return await new_conn.fetchval(query, patient_id)

    async def _get_settings(self, conn, patient_id: str) -> Optional[Dict[str, Any]]:
        row = await conn.fetchrow("SELECT * FROM patient_settings WHERE patient_id = $1", patient_id)
        return dict(row) if row else None

    async def _save_measurement(self, conn, patient_id: str, hr: int, inactivity: int, status: str) -> datetime:
        query = """
            INSERT INTO measurements (patient_id, heart_rate, inactivity_seconds, status, measured_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING measured_at
        """
        return await conn.fetchval(query, patient_id, hr, inactivity, status)

    async def _create_alert(self, conn, patient_id: str, message: str):
        query = """
            INSERT INTO emergency_logs (patient_id, message, created_at)
            VALUES ($1, $2, NOW())
            RETURNING id, patient_id, message, created_at
        """
        row = await conn.fetchrow(query, patient_id, message)
        if row:
            alert_data = dict(row)
            alert_data['patient_id'] = str(alert_data['patient_id'])
            alert_data['created_at'] = alert_data['created_at'].isoformat()
            await conn.execute(
                "SELECT pg_notify('alert_updates', $1)", 
                json.dumps(alert_data)
            )
