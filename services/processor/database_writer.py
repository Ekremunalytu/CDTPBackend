import asyncpg
import os
import json
from datetime import datetime

class DatabaseWriter:
    def __init__(self):
        self.db_url = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        self.pool = None

    async def connect(self):
        if not self.pool:
            try:
                self.pool = await asyncpg.create_pool(self.db_url)
                print("DB Writer Connected")
            except Exception as e:
                print(f"DB Connection Failed: {e}")

    async def save_measurement(self, patient_id: str, heart_rate: int, inactivity_seconds: int, status: str):
        if not self.pool:
            await self.connect()
        
        query = """
            INSERT INTO measurements (patient_id, heart_rate, inactivity_seconds, status, measured_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query, patient_id, heart_rate, inactivity_seconds, status)
                print(f"Saved measurement for {patient_id}: {status}")
        except Exception as e:
            print(f"Failed to save measurement: {e}")

    async def create_alert(self, patient_id: str, message: str):
        if not self.pool:
            await self.connect()

        query = """
            INSERT INTO emergency_logs (patient_id, message, created_at)
            VALUES ($1, $2, NOW())
        """
        try:
            async with self.pool.acquire() as connection:
                await connection.execute(query, patient_id, message)
                print(f"ALERT CREATED for {patient_id}: {message}")
        except Exception as e:
            print(f"Failed to create alert: {e}")
