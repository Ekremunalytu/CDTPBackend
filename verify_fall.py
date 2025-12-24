import requests
import json
import time

URL = "http://localhost:8001/api/v1/ingest"

# Patient ID must match the one inserted into DB
PATIENT_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

fall_data = {
    "patient_id": PATIENT_ID,
    "timestamp": time.time(),
    "accelerometer": {"x": 0.5, "y": 0.5, "z": 3.5}, # SMV > 3.0g -> FALL
    "gyroscope": {"x": 0.01, "y": 0.02, "z": 0.01},
    "ppg_raw": [2048, 2050, 2060, 2055, 2040]
}

def trigger_fall():
    try:
        print(f"Sending FALL data to {URL}...")
        response = requests.post(URL, json=fall_data)
        
        if response.status_code == 200:
            print("✅ Data sent! Now check the database for 'CRITICAL' status.")
        else:
            print(f"❌ Failed! Status: {response.status_code}, Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error!")

if __name__ == "__main__":
    trigger_fall()
