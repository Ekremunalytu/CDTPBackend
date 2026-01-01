import requests
import json
import time

URL = "http://localhost:8001/api/v1/ingest"

dummy_data = {
    "patient_id": "test-patient-001",
    "timestamp": time.time(),
    "accelerometer": {"x": 0.1, "y": 9.8, "z": 0.2},
    "gyroscope": {"x": 0.01, "y": 0.02, "z": 0.01},
    "ppg_raw": [2048, 2050, 2060, 2055, 2040]
}

def test_ingestion():
    try:
        print(f"Sending data to {URL}...")
        response = requests.post(URL, json=dummy_data)
        
        if response.status_code == 200:
            print("✅ Success! Response:", response.json())
        else:
            print(f"❌ Failed! Status: {response.status_code}, Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error! Is the Ingestion Service running? (docker-compose up)")

if __name__ == "__main__":
    test_ingestion()
