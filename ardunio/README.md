# 🩺 CDTP ESP32 Sağlık İzleme Firmware

## Donanım Gereksinimleri

| Bileşen | Model | Açıklama |
|---------|-------|----------|
| MCU | ESP32-C3-Mini-1 | BLE 5.0 destekli |
| İvme/Gyro | MPU6050 | 6-axis sensör |
| Nabız/SpO2 | MAX30100 | PPG sensör |
| Buton | Any | Acil durum butonu |

## Pin Bağlantıları

```
ESP32-C3-Mini-1        MPU6050         MAX30100
-----------------      -------         --------
GPIO6 (SDA)    ───────→ SDA    ───────→ SDA
GPIO7 (SCL)    ───────→ SCL    ───────→ SCL
3.3V           ───────→ VCC    ───────→ VIN
GND            ───────→ GND    ───────→ GND

GPIO2          ───────→ BUTTON (diğer ucu GND'ye)
GPIO8          ───────→ LED (opsiyonel)
```

## Arduino IDE Kurulumu

### 1. ESP32 Board Desteği

Preferences → Additional Board URLs:
```
https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
```

Board Manager → "ESP32" ara → Kur

Board seç: **ESP32C3 Dev Module**

### 2. Gerekli Kütüphaneler

Library Manager'dan kur:

| Kütüphane | Arama Terimi |
|-----------|--------------|
| MPU6050 | `MPU6050` (Electronic Cats) |
| MAX30100 | `MAX30100lib` (OXullo) |

> Not: BLE kütüphanesi ESP32 core ile birlikte gelir.

### 3. Board Ayarları

| Ayar | Değer |
|------|-------|
| Board | ESP32C3 Dev Module |
| USB CDC On Boot | Enabled |
| CPU Frequency | 160MHz |
| Flash Mode | QIO |
| Flash Size | 4MB |
| Partition Scheme | Default |

## Yükleme

1. ESP32'yi USB ile bağla
2. Port seç (COM* veya /dev/tty.*)
3. Upload butonuna bas
4. Serial Monitor aç (115200 baud)

## Test

Serial Monitor çıktısı:
```
========================================
  CDTP Sağlık İzleme Sistemi v1.0
  ESP32-C3-Mini-1 + BLE
========================================

MPU6050 başlatılıyor... OK ✓
MAX30100 başlatılıyor... OK ✓
BLE başlatılıyor... OK ✓

📡 BLE yayını başladı: CDTP-Watch
📱 Mobil uygulamadan bağlanabilirsiniz.
```

## BLE Servisleri

| UUID | Açıklama |
|------|----------|
| `0000180D-...` | Heart Rate Service |
| `00002A37-...` | Sensor Data (notify) |
| `00002A38-...` | Alarm (notify) |

## Veri Formatı

```json
{
  "acc": {"x": 0.1, "y": 0.2, "z": 0.98},
  "gyro": {"x": 1.2, "y": -0.5, "z": 0.1},
  "ppg": 2000,
  "hr": 72,
  "spo2": 98,
  "state": "NORMAL"
}
```

## Durumlar

| State | Açıklama |
|-------|----------|
| NORMAL | Normal çalışma |
| IMPACT | Darbe algılandı |
| FALL_ALARM | Düşme onaylandı |
| MANUAL_ALARM | Buton basıldı |

## Sorun Giderme

### "MAX30100 bulunamadı"
- I2C bağlantılarını kontrol et
- 3.3V beslemeden emin ol
- Pull-up dirençleri ekle (4.7kΩ SDA/SCL → 3.3V)

### "MPU6050 FAILED"
- I2C adresini kontrol et (0x68 veya 0x69)
- Besleme voltajını ölç

### BLE bağlantısı kurulamıyor
- Telefon Bluetooth açık mı?
- Konum izni verildi mi?
- Diğer bağlantıları kes
