"""
Sensör Simulator

Gerçek ESP32 cihazı simüle eder. Mobil uygulama formatında (array) veri gönderir.
"""
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

# Simulation window size (number of samples per packet)
WINDOW_SIZE = 25  # 25 sample = 1 saniye @ 25Hz

def handle_sigterm(*args):
    print("Simulator stopping...")
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
signal.signal(signal.SIGINT, handle_sigterm)


def generate_normal_data(time_offset):
    """Normal durum: ~1g yerçekimi, düşük hareket"""
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {
            "x": [0.05 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)],
            "y": [0.10 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)],
            "z": [0.98 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)]
        },
        "gyroscope": {
            "x": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)],
            "y": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)],
            "z": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)]
        },
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 5)) for i in range(WINDOW_SIZE)]
    }


def generate_fall_data(time_offset):
    """
    Düşme senaryosu: 
    - İlk 5 sample: free-fall (SMV < 0.5g)
    - Sonraki 5 sample: impact (SMV > 3g)
    - Kalan samplelar: stillness (SMV ~ 1g)
    """
    acc_x, acc_y, acc_z = [], [], []
    
    # Phase 1: Free-fall (5 samples)
    for _ in range(5):
        acc_x.append(random.uniform(0.0, 0.2))
        acc_y.append(random.uniform(0.0, 0.2))
        acc_z.append(random.uniform(0.0, 0.3))  # Total SMV < 0.5
    
    # Phase 2: Impact (5 samples)
    for _ in range(5):
        acc_x.append(random.uniform(2.0, 3.0))
        acc_y.append(random.uniform(1.5, 2.5))
        acc_z.append(random.uniform(1.0, 2.0))  # Total SMV > 3g
    
    # Phase 3: Stillness (remaining samples)
    for _ in range(WINDOW_SIZE - 10):
        acc_x.append(random.uniform(0.0, 0.1))
        acc_y.append(random.uniform(0.0, 0.1))
        acc_z.append(random.uniform(0.95, 1.05))  # ~1g
    
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {"x": acc_x, "y": acc_y, "z": acc_z},
        "gyroscope": {
            "x": [random.uniform(1.0, 3.0) for _ in range(WINDOW_SIZE)],
            "y": [random.uniform(1.0, 3.0) for _ in range(WINDOW_SIZE)],
            "z": [random.uniform(1.0, 3.0) for _ in range(WINDOW_SIZE)]
        },
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 5)) for i in range(WINDOW_SIZE)]
    }


def generate_tachycardia_data(time_offset):
    """Yüksek kalp atışı senaryosu: Daha hızlı PPG dalgası"""
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {
            "x": [0.05 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)],
            "y": [0.10 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)],
            "z": [0.98 + random.uniform(-0.02, 0.02) for _ in range(WINDOW_SIZE)]
        },
        "gyroscope": {
            "x": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)],
            "y": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)],
            "z": [0.01 + random.uniform(-0.01, 0.01) for _ in range(WINDOW_SIZE)]
        },
        # Faster wave = higher BPM
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 2)) for i in range(WINDOW_SIZE)]
    }


def generate_inactivity_data(time_offset):
    """Hareketsizlik senaryosu: Tamamen sabit ~1g"""
    return {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": {
            "x": [0.0 for _ in range(WINDOW_SIZE)],
            "y": [0.0 for _ in range(WINDOW_SIZE)],
            "z": [1.0 for _ in range(WINDOW_SIZE)]  # Pure 1g downward
        },
        "gyroscope": {
            "x": [0.0 for _ in range(WINDOW_SIZE)],
            "y": [0.0 for _ in range(WINDOW_SIZE)],
            "z": [0.0 for _ in range(WINDOW_SIZE)]
        },
        "ppg_raw": [2000 + int(200 * math.sin((time_offset + i) / 5)) for i in range(WINDOW_SIZE)]
    }


def run_simulation():
    print(f"Starting Sensor Simulation for Patient: {PATIENT_ID}")
    print(f"Target URL: {API_URL}")
    print(f"Format: Array (Mobile App processed)")
    
    # Wait for service to be up
    time.sleep(5)
    
    counter = 0
    mode = "NORMAL"
    
    while True:
        try:
            counter += 1
            cycle = counter % 200
            
            # State machine
            if 150 < cycle < 160:
                mode = "TACHYCARDIA"
            elif cycle == 190:
                mode = "FALL"
                print("\n>> TRIGGERING FALL EVENT")
            elif 180 < cycle < 190:
                mode = "INACTIVITY"
            else:
                mode = "NORMAL"
            
            # Generate Data
            if mode == "NORMAL":
                data = generate_normal_data(counter)
            elif mode == "FALL":
                data = generate_fall_data(counter)
            elif mode == "TACHYCARDIA":
                data = generate_tachycardia_data(counter)
            elif mode == "INACTIVITY":
                data = generate_inactivity_data(counter)
                
            # Send Data
            resp = requests.post(API_URL, json=data, timeout=2)
            if resp.status_code == 200:
                print(".", end="", flush=True)
            else:
                print(f"X({resp.status_code})", end="", flush=True)

        except Exception as e:
            print(f"\nConnection Error: {e}")
            time.sleep(2)
            
        time.sleep(1.0 / FREQUENCY_HZ)


if __name__ == "__main__":
    run_simulation()
