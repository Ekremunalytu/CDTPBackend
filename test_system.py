#!/usr/bin/env python3
"""
CDTP Sistem Test Script
Tüm senaryoları test eder: Normal, Düşme, Yüksek Nabız, Hareketsizlik
"""
import requests
import time
import json

URL = "http://localhost:8001/api/v1/ingest"
PATIENT_ID = "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11"

def send_data(scenario_name, accelerometer, gyroscope, ppg_raw):
    """Veri gönderir ve sonucu gösterir"""
    data = {
        "patient_id": PATIENT_ID,
        "timestamp": time.time(),
        "accelerometer": accelerometer,
        "gyroscope": gyroscope,
        "ppg_raw": ppg_raw
    }
    
    try:
        resp = requests.post(URL, json=data, timeout=5)
        status = "✅" if resp.status_code == 200 else "❌"
        print(f"{status} [{scenario_name}] Status: {resp.status_code}")
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ [{scenario_name}] Hata: {e}")
        return False

def test_normal():
    """Normal veri - Alert üretmemeli"""
    print("\n🧪 Test 1: Normal Veri")
    return send_data(
        "NORMAL",
        accelerometer={"x": [0.1, 0.1, 0.1], "y": [0.2, 0.2, 0.2], "z": [0.98, 0.98, 0.98]},
        gyroscope={"x": [0.01], "y": [0.01], "z": [0.01]},
        ppg_raw=[2000, 2050, 2100, 2050, 2000, 1950, 1900, 1950, 2000, 2050,
                 2100, 2050, 2000, 1950, 1900, 1950, 2000, 2050, 2100, 2050,
                 2000, 1950, 1900, 1950, 2000]  # Normal sinüs dalga
    )

def test_fall():
    """Düşme simülasyonu - CRITICAL alert üretmeli"""
    print("\n🧪 Test 2: Düşme Tespiti")
    # Freefall -> Impact -> Stillness pattern
    return send_data(
        "FALL",
        accelerometer={
            "x": [0.1, 0.1, 0.3, 3.5, 4.0, 0.5, 0.1, 0.1, 0.1, 0.1],  # Impact at 3.5-4g
            "y": [0.1, 0.1, 0.2, 3.0, 3.5, 0.3, 0.1, 0.1, 0.1, 0.1],
            "z": [0.3, 0.2, 0.1, 2.5, 3.0, 0.9, 0.98, 0.98, 0.98, 0.98]  # Stillness after
        },
        gyroscope={"x": [2.0], "y": [2.0], "z": [2.0]},
        ppg_raw=[2000] * 25
    )

def test_high_bpm():
    """Yüksek nabız simülasyonu - CRITICAL alert üretmeli"""
    print("\n🧪 Test 3: Yüksek Nabız (Taşikardi)")
    # Hızlı PPG dalgası -> yüksek BPM
    fast_ppg = []
    for i in range(25):
        fast_ppg.append(2000 + int(100 * (1 if i % 2 == 0 else -1)))  # Çok hızlı dalga
    
    return send_data(
        "HIGH_BPM",
        accelerometer={"x": [0.1], "y": [0.2], "z": [0.98]},
        gyroscope={"x": [0.01], "y": [0.01], "z": [0.01]},
        ppg_raw=fast_ppg
    )

def test_low_bpm():
    """Düşük nabız simülasyonu - CRITICAL alert üretmeli"""
    print("\n🧪 Test 4: Düşük Nabız (Bradikardi)")
    # Yavaş PPG dalgası -> düşük BPM
    return send_data(
        "LOW_BPM",
        accelerometer={"x": [0.1], "y": [0.2], "z": [0.98]},
        gyroscope={"x": [0.01], "y": [0.01], "z": [0.01]},
        ppg_raw=[2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000,
                 2100, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000, 2000,
                 2000, 2000, 2000, 2000, 2000]  # Çok az peak
    )

def check_alerts():
    """Son alert'leri kontrol eder"""
    print("\n📋 Son Oluşan Alert'ler:")
    try:
        # Core API üzerinden dashboard endpoint'ini kontrol et
        resp = requests.get("http://localhost:8000/api/dashboard/alerts", timeout=5)
        if resp.status_code == 200:
            alerts = resp.json()
            if alerts:
                for alert in alerts[:5]:  # Son 5 alert
                    print(f"  🚨 {alert.get('message', 'N/A')} - {alert.get('created_at', 'N/A')}")
            else:
                print("  (Henüz alert yok)")
        else:
            print(f"  ⚠️ Dashboard API yanıt vermedi: {resp.status_code}")
    except Exception as e:
        print(f"  ⚠️ Dashboard kontrol edilemedi: {e}")

def check_processor_status():
    """Processor loglarını kontrol eder"""
    print("\n📊 Processor Durumu:")
    print("  💡 Processor loglarını görmek için: docker-compose logs -f processor")

def main():
    print("=" * 50)
    print("🏥 CDTP Sistem Test Script")
    print("=" * 50)
    
    # Servis kontrolü
    print("\n🔍 Servis Kontrolü...")
    try:
        resp = requests.get("http://localhost:8001/health", timeout=3)
        if resp.status_code == 200:
            print("✅ Ingestion servisi çalışıyor")
        else:
            print("❌ Ingestion servisi yanıt vermiyor")
            return
    except:
        print("❌ Servisler çalışmıyor! Önce './start_all.sh' çalıştırın")
        return
    
    # Testleri çalıştır
    results = []
    results.append(("Normal Veri", test_normal()))
    time.sleep(1)  # Processor'ın işlemesi için bekle
    
    results.append(("Düşme Tespiti", test_fall()))
    time.sleep(1)
    
    results.append(("Yüksek Nabız", test_high_bpm()))
    time.sleep(1)
    
    results.append(("Düşük Nabız", test_low_bpm()))
    time.sleep(2)  # Son işleme için biraz daha bekle
    
    # Sonuçları göster
    print("\n" + "=" * 50)
    print("📊 TEST SONUÇLARI")
    print("=" * 50)
    for name, passed in results:
        status = "✅ BAŞARILI" if passed else "❌ BAŞARISIZ"
        print(f"  {name}: {status}")
    
    check_alerts()
    check_processor_status()
    
    print("\n" + "=" * 50)
    print("💡 İPUÇLARI:")
    print("  - Processor logları: docker-compose logs -f processor")
    print("  - Tüm loglar: docker-compose logs -f")
    print("  - Alert'ler DB'de: emergency_logs tablosu")
    print("=" * 50)

if __name__ == "__main__":
    main()
