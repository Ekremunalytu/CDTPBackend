import requests
import time
import random
import math
import sys

URL = "http://localhost:8001/api/v1/ingest"
PATIENT_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

def generate_normal_data():
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 0.1, "y": 0.2, "z": 0.98}, # ~1g
        "gyroscope": {"x": 0.01, "y": 0.01, "z": 0.01},
        "ppg_raw": [2000 + int(100 * math.sin(i/5)) for i in range(25)] # Normal wave
    }

def generate_fall_data():
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 2.5, "y": 2.5, "z": 2.5}, # High SMV
        "gyroscope": {"x": 2.0, "y": 2.0, "z": 2.0},
        "ppg_raw": [2000 + int(100 * math.sin(i/5)) for i in range(25)]
    }

def generate_tachycardia_data():
    # Fast wave for high BPM
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": 0.1, "y": 0.2, "z": 0.98},
        "gyroscope": {"x": 0.01, "y": 0.01, "z": 0.01},
        "ppg_raw": [2000 + int(100 * math.sin(i/2)) for i in range(25)] 
    }

def run_simulation():
    print("Starting Sensor Simulation...")
    print("Press Ctrl+C to stop.")
    
    mode = "NORMAL"
    counter = 0
    
    try:
        while True:
            # Change mode occasionally for demo
            counter += 1
            if counter % 10 == 0: # More frequent for demo
                mode = "FALL"
                print("\n!!! SIMULATING FALL !!!\n")
            elif counter % 15 == 0:
                mode = "TACHYCARDIA"
                print("\n!!! SIMULATING TACHYCARDIA !!!\n")
            else:
                mode = "NORMAL"
            
            if mode == "NORMAL":
                data = generate_normal_data()
            elif mode == "FALL":
                data = generate_fall_data()
            elif mode == "TACHYCARDIA":
                data = generate_tachycardia_data()
                
            try:
                resp = requests.post(URL, json=data)
                if resp.status_code != 200:
                    print(f"Error: {resp.status_code}")
                else:
                    # Print summary of sent data
                    hr_avg = sum(data['ppg_raw']) / len(data['ppg_raw']) # Rough proxy for visualization
                    acc = data['accelerometer']
                    print(f"Sent -> Mode: {mode:<12} | Acc: x={acc['x']:.1f}, y={acc['y']:.1f}, z={acc['z']:.1f} | PPG Avg: {hr_avg:.0f}")
            except Exception as e:
                print(f"Connection Error: {e}")
                
            time.sleep(0.2) # 5 Hz
            
    except KeyboardInterrupt:
        print("\nSimulation Stopped.")

if __name__ == "__main__":
    run_simulation()
