import requests
import time
import random
import math
import os
import signal
import sys

# Configuration from ENV
API_URL = os.getenv("INGESTION_URL", "http://ingestion:8000/api/v1/ingest")
PATIENT_ID = os.getenv("PATIENT_ID", "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11")
FREQUENCY_HZ = float(os.getenv("FREQUENCY_HZ", "5.0"))

def handle_sigterm(*args):
    print("Simulator stopping...")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)

def generate_normal_data(time_offset):
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 0.05, "y": 0.1, "z": 0.98}, # Approx 1g
        "gyroscope": {"x": 0.01, "y": 0.01, "z": 0.01},
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 5)) for i in range(25)]
    }

def generate_fall_data(time_offset):
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 3.5, "y": 1.5, "z": 0.5}, # High impact
        "gyroscope": {"x": 2.5, "y": 2.5, "z": 2.5},
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 5)) for i in range(25)]
    }

def generate_tachycardia_data(time_offset):
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 0.05, "y": 0.1, "z": 0.98},
        "gyroscope": {"x": 0.01, "y": 0.01, "z": 0.01},
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 2)) for i in range(25)] # Faster wave
    }

def run_simulation():
    print(f"Starting Sensor Simulation for Patient: {PATIENT_ID}")
    print(f"Target URL: {API_URL}")
    
    # Wait for service to be up
    time.sleep(5) 
    
    counter = 0
    mode = "NORMAL"
    
    while True:
        try:
            counter += 1
            # Simple state machine for demo purposes
            # 0-50: Normal
            # 50-55: High HR
            # 55-100: Normal
            # 100-102: Fall
            cycle = counter % 200
            
            if 150 < cycle < 160:
                mode = "TACHYCARDIA"
            elif cycle == 190:
                mode = "FALL"
                print(">> TRIGGERING FALL EVENT")
            else:
                mode = "NORMAL"
            
            # Generate Data
            if mode == "NORMAL":
                data = generate_normal_data(counter)
            elif mode == "FALL":
                data = generate_fall_data(counter)
            elif mode == "TACHYCARDIA":
                data = generate_tachycardia_data(counter)
                
            # Send Data
            resp = requests.post(API_URL, json=data, timeout=2)
            if resp.status_code == 200:
                # print(".", end="", flush=True)
                pass
            else:
                print(f"X ({resp.status_code})", end="", flush=True)

        except Exception as e:
            print(f"Connection Error: {e}")
            time.sleep(2)
            
        time.sleep(1.0 / FREQUENCY_HZ)

if __name__ == "__main__":
    run_simulation()
