# ESP32 Geliştirme Rehberi

Bu doküman, CDTP projesi için ESP32 gömülü yazılım geliştirme sürecini açıklamaktadır.

---

## 1. Gerekli Yazılımlar

| Yazılım | İndirme Linki | Açıklama |
|---------|---------------|----------|
| **Arduino IDE 2.x** | https://www.arduino.cc/en/software | Kod yazma ve yükleme |
| **USB Driver** | CP210x veya CH340 (ESP32 modülüne göre) | USB bağlantısı için |

---

## 2. Arduino IDE Kurulumu

### Adım 1: ESP32 Board Ekle

1. Arduino IDE → **File** → **Preferences**
2. "Additional Board Manager URLs" alanına şunu ekle:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. **OK**'a bas

### Adım 2: ESP32 Board Yükle

1. **Tools** → **Board** → **Board Manager**
2. Arama kutusuna "ESP32" yaz
3. "**ESP32 by Espressif Systems**" bul ve **Install** tıkla
4. Kurulum tamamlandıktan sonra:
   - **Tools** → **Board** → **ESP32 Dev Module** seç

### Adım 3: Kütüphaneleri Yükl

1. **Sketch** → **Include Library** → **Manage Libraries**
2. Şu kütüphaneleri ara ve yükle:
   - `MPU6050` by Electronic Cats
   - `MAX30105` by SparkFun (PPG sensörü için)

---

## 3. Donanım Bağlantıları

### Pin Diyagramı

```
ESP32                    Sensörler
─────                    ────────
                    ┌──────────────┐
GPIO 21 (SDA) ────────→ MPU-6050 SDA
                    │   MAX30102 SDA
                    └──────────────┘
                    ┌──────────────┐
GPIO 22 (SCL) ────────→ MPU-6050 SCL
                    │   MAX30102 SCL
                    └──────────────┘
3.3V ─────────────────→ VCC (her iki sensör)
GND ──────────────────→ GND (her iki sensör)
GPIO 2 ───────────────→ Acil Buton (diğer ucu GND'ye)
```

### Bağlantı Şeması

```
                    ┌─────────────┐
                    │   ESP32     │
                    │             │
         ┌──────────┤ GPIO21(SDA) │
         │    ┌─────┤ GPIO22(SCL) │
         │    │     │ 3.3V        ├─────────┐
         │    │     │ GND         ├─────┐   │
         │    │     │ GPIO2       ├──┐  │   │
         │    │     └─────────────┘  │  │   │
         │    │                      │  │   │
    ┌────┴────┴──┐    ┌──────────┐   │  │   │
    │  MPU-6050  │    │ MAX30102 │   │  │   │
    │            │    │ (PPG)    │   │  │   │
    │ SDA  SCL   │    │ SDA  SCL │   │  │   │
    │ VCC  GND   │    │ VIN  GND │   │  │   │
    └──┬───┬─────┘    └──┬───┬───┘   │  │   │
       │   │             │   │       │  │   │
       │   └─────────────┼───┼───────┼──┘   │
       └─────────────────┴───┴───────┴──────┘

    ┌────────┐
    │ BUTON  │──── GPIO2
    │        │──── GND
    └────────┘
```

> **Not:** MPU-6050 ve MAX30102 aynı I2C hattını paylaşır (farklı I2C adresleri var).
> - MPU-6050 adresi: `0x68`
> - MAX30102 adresi: `0x57`

---

## 4. Kod Dosyası

Mevcut ESP32 kodu şu konumda:

```
/CDTPBackend/dusme_ve_acil_durum_butonu.ino
```

Bu dosyayı Arduino IDE ile açabilirsin.

---

## 5. Kod Yükleme Adımları

1. **ESP32'yi USB ile bilgisayara bağla**

2. **Arduino IDE'de ayarları yap:**
   - **Tools** → **Board** → **ESP32 Dev Module**
   - **Tools** → **Port** → Uygun portu seç:
     - Mac: `/dev/cu.usbserial-XXXX`
     - Windows: `COM3`, `COM4`, vb.
     - Linux: `/dev/ttyUSB0`

3. **Compile et:**
   - **✓ (Verify)** butonuna tıkla
   - Hata yoksa "Done compiling" mesajı görürsün

4. **ESP32'ye yükle:**
   - **→ (Upload)** butonuna tıkla
   - "Connecting..." mesajı görünce ESP32'deki **BOOT** butonuna basılı tut
   - Yükleme tamamlanınca butonu bırak

5. **Serial Monitor'ı aç:**
   - **Tools** → **Serial Monitor**
   - Baud rate: **115200**
   - Çıktıları gözlemle

---

## 6. Mevcut Kodda Yapılar

### ✅ Mevcut Özellikler

| Özellik | Durum |
|---------|-------|
| MPU-6050 ivme okuma | ✅ Var |
| MPU-6050 jiroskop okuma | ✅ Var |
| Düşme tespiti (impact + stillness) | ✅ Var |
| Acil durum butonu | ✅ Var |
| Serial Monitor çıktısı | ✅ Var |

### ❌ Eksik Özellikler

| Özellik | Açıklama |
|---------|----------|
| BLE Server | Mobil app ile iletişim için gerekli |
| MAX30102 (PPG) | Nabız ölçümü için gerekli |
| JSON veri paketi | Backend formatına uygun veri gönderimi |

---

## 7. Eklenmesi Gereken Kodlar

### 7.1 BLE Server Kurulumu

`setup()` fonksiyonundan önce ekle:

```cpp
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

// GATT Service ve Characteristic UUID'leri
#define SERVICE_UUID        "0000180D-0000-1000-8000-00805f9b34fb"
#define CHARACTERISTIC_UUID "00002A37-0000-1000-8000-00805f9b34fb"

BLECharacteristic *pCharacteristic;
bool bleConnected = false;

// Bağlantı callback'leri
class MyServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        bleConnected = true;
        Serial.println("📱 Mobil app bağlandı!");
    }
    void onDisconnect(BLEServer* pServer) {
        bleConnected = false;
        Serial.println("📱 Mobil app bağlantısı kesildi!");
        // Yeniden advertise başlat
        BLEDevice::startAdvertising();
    }
};
```

`setup()` fonksiyonuna ekle:

```cpp
// BLE başlat
BLEDevice::init("CDTP-Watch");  // Cihaz adı

// BLE Server oluştur
BLEServer *pServer = BLEDevice::createServer();
pServer->setCallbacks(new MyServerCallbacks());

// Service oluştur
BLEService *pService = pServer->createService(SERVICE_UUID);

// Characteristic oluştur (READ + NOTIFY)
pCharacteristic = pService->createCharacteristic(
    CHARACTERISTIC_UUID,
    BLECharacteristic::PROPERTY_READ |
    BLECharacteristic::PROPERTY_NOTIFY
);

// Descriptor ekle (NOTIFY için gerekli)
pCharacteristic->addDescriptor(new BLE2902());

// Service'i başlat
pService->start();

// Advertising başlat (cihazı görünür yap)
BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
pAdvertising->addServiceUUID(SERVICE_UUID);
pAdvertising->setScanResponse(true);
pAdvertising->start();

Serial.println("✅ BLE Server hazır, mobil app bağlanabilir!");
```

### 7.2 Veri Gönderimi (loop içinde)

`loop()` fonksiyonunda periyodik rapor kısmını güncelle:

```cpp
// 5) Log ve BLE gönderimi
if (now - tsLastReport >= REPORTING_PERIOD_MS) {
    // JSON formatında veri hazırla
    String jsonData = "{";
    jsonData += "\"acc\":{\"x\":" + String(ax, 3) + ",\"y\":" + String(ay, 3) + ",\"z\":" + String(az, 3) + "},";
    jsonData += "\"gyro\":{\"x\":" + String(gx, 1) + ",\"y\":" + String(gy, 1) + ",\"z\":" + String(gz, 1) + "},";
    jsonData += "\"state\":\"" + String((state == NORMAL) ? "NORMAL" : 
                 (state == IMPACT_DETECTED) ? "IMPACT" :
                 (state == FALL_ALARM) ? "FALL_ALARM" : "MANUAL_ALARM") + "\",";
    jsonData += "\"ppg\":2000";  // TODO: MAX30102'den oku
    jsonData += "}";
    
    // BLE ile gönder
    if (bleConnected) {
        pCharacteristic->setValue(jsonData.c_str());
        pCharacteristic->notify();
        Serial.println("📤 BLE gönderildi: " + jsonData);
    }
    
    // Serial'a da yaz
    Serial.println(jsonData);
    
    tsLastReport = now;
}
```

### 7.3 MAX30102 PPG Sensörü (Opsiyonel)

```cpp
#include "MAX30105.h"

MAX30105 particleSensor;

// setup() içinde:
if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 bulunamadı!");
}
particleSensor.setup();

// loop() içinde:
long irValue = particleSensor.getIR();  // PPG değeri
```

---

## 8. Test Etme

### Serial Monitor Çıktısı (Beklenen)

```
ESP32 + MPU6050 (DUSME + BUTON) baslatiliyor...
MPU6050 OK
✅ BLE Server hazır, mobil app bağlanabilir!
Buton: GPIO13 -> GND (INPUT_PULLUP). Basinca MANUAL ALARM.
Düşme: |a|>2.5g => impact, sonra 5sn abs(|a|-1g)<0.08 => FALL ALARM

{"acc":{"x":0.02,"y":-0.05,"z":0.98},"gyro":{"x":0.1,"y":-0.3,"z":0.2},"state":"NORMAL","ppg":2000}
{"acc":{"x":0.03,"y":-0.04,"z":0.99},"gyro":{"x":0.2,"y":-0.2,"z":0.1},"state":"NORMAL","ppg":2000}
...
```

### BLE Test (Mobil Cihaz)

1. Telefona **nRF Connect** uygulamasını indir (Play Store / App Store)
2. Uygulamayı aç, **Scan** yap
3. "**CDTP-Watch**" cihazını bul ve **Connect** tıkla
4. Services altında UUID'yi gör
5. Notify'ı aç → Veri akışını gör

---

## 9. Sorun Giderme

### ESP32 algılanmıyor

- USB kablosunun veri kablosu olduğundan emin ol (şarj kablosu değil)
- USB driver'ı yükle (CP210x veya CH340)
- Farklı USB portu dene

### Upload sırasında "Connecting..." takılıyor

- ESP32'deki **BOOT** butonuna basılı tut
- Upload bitene kadar bırakma

### MPU6050 FAILED hatası

- I2C bağlantılarını kontrol et (SDA, SCL)
- Sensör beslemesini kontrol et (3.3V)
- `Wire.begin(6, 7)` pin numaralarını ESP32 modülüne göre ayarla

### BLE görünmüyor

- ESP32'yi resetle
- Telefonda Bluetooth açık mı kontrol et
- Location izni gerekebilir (Android)

---

## 10. Checklist

### Kurulum
- [ ] Arduino IDE 2.x kuruldu
- [ ] ESP32 board eklendi
- [ ] MPU6050 kütüphanesi yüklendi
- [ ] USB driver kuruldu

### Donanım
- [ ] MPU-6050 bağlandı (I2C)
- [ ] MAX30102 bağlandı (opsiyonel)
- [ ] Acil buton bağlandı
- [ ] ESP32 USB ile bilgisayara bağlı

### Yazılım
- [ ] Kod derlendi (hata yok)
- [ ] ESP32'ye yüklendi
- [ ] Serial Monitor'da çıktı görünüyor
- [ ] BLE Server çalışıyor
- [ ] nRF Connect ile test edildi

### Entegrasyon
- [ ] Mobil app BLE ile bağlanabiliyor
- [ ] Veri JSON formatında geliyor
- [ ] Backend'e iletiliyor

---

## 11. Veri Formatı (Backend Uyumlu)

Mobil app bu veriyi alıp backend'e şu formatta göndermeli:

```json
{
    "patient_id": "a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11",
    "timestamp": 1735560600.123,
    "accelerometer": {
        "x": [0.02, 0.03, 0.02],
        "y": [-0.05, -0.04, -0.05],
        "z": [0.98, 0.99, 0.98]
    },
    "gyroscope": {
        "x": [0.1, 0.2, 0.1],
        "y": [-0.3, -0.2, -0.3],
        "z": [0.2, 0.1, 0.2]
    },
    "ppg_raw": [2000, 2050, 2100, 2050, 2000]
}
```

**Endpoint:** `POST http://<BACKEND_IP>:8001/api/v1/ingest`
