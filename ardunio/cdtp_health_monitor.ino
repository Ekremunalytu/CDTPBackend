/*
 * CDTP Sağlık İzleme Sistemi - ESP32 Firmware
 * 
 * Donanım:
 * - ESP32-C3-Mini-1
 * - MPU6050 (6-axis accelerometer + gyroscope)
 * - MAX30100 (pulse oximeter + heart rate)
 * - Button (acil durum)
 * 
 * Kütüphaneler:
 * - Adafruit MPU6050
 * - MAX30100lib by OXullo
 */

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include "MAX30100_PulseOximeter.h"

// ==================== PIN TANIMLARI ====================
#define SDA_PIN 6 
#define SCL_PIN 7
#define BUTTON_PIN 2
#define LED_PIN 8  // ESP32-C3 dahili LED (varsa, yoksa -1 yap)

// ==================== BLE AYARLARI ====================
#define DEVICE_NAME "CDTP-Watch"

// Heart Rate Service (standart BLE UUID)
#define SERVICE_UUID        "0000180D-0000-1000-8000-00805f9b34fb"
// Sensor Data Characteristic
#define SENSOR_CHAR_UUID    "00002A37-0000-1000-8000-00805f9b34fb"
// Alarm Characteristic  
#define ALARM_CHAR_UUID     "00002A38-0000-1000-8000-00805f9b34fb"

// ==================== DÜŞME TESPİT EŞİKLERİ ====================
const float FALL_PEAK_G = 2.5f;          // Darbe eşiği (g)
const uint32_t STILL_TIME_MS = 5000;     // Hareketsizlik süresi (ms)
const float STILL_DELTA_G = 0.08f;       // |a|-1g toleransı (g)

// ==================== ZAMANLAMALAR ====================
#define SENSOR_PERIOD_MS 200     // Sensör okuma periyodu (5 Hz)
#define BLE_NOTIFY_PERIOD_MS 500 // BLE bildirim periyodu (2 Hz)
#define PPG_SAMPLE_PERIOD_MS 20  // MAX30100 örnekleme (50 Hz)

// ==================== GLOBAL DEĞİŞKENLER ====================
Adafruit_MPU6050 mpu;
PulseOximeter pox;
bool mpuReady = false;
bool poxReady = false;

BLEServer* pServer = NULL;
BLECharacteristic* pSensorCharacteristic = NULL;
BLECharacteristic* pAlarmCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

// Durum makinesi
enum State { NORMAL, IMPACT_DETECTED, FALL_ALARM, MANUAL_ALARM };
State currentState = NORMAL;

// Zamanlamalar
uint32_t lastSensorRead = 0;
uint32_t lastBleNotify = 0;
uint32_t lastPpgSample = 0;
uint32_t impactTime = 0;
uint32_t stillStartTime = 0;
bool stillRunning = false;

// Sensör verileri
float accX = 0, accY = 0, accZ = 0;
float gyroX = 0, gyroY = 0, gyroZ = 0;
float accMagnitude = 1.0f;
int heartRate = 0;
int spO2 = 0;

// Buton debounce
bool lastButtonState = true;
uint32_t lastDebounceTime = 0;
const uint32_t DEBOUNCE_DELAY = 50;

// ==================== BLE CALLBACKS ====================
class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
        Serial.println("📱 Mobil app bağlandı!");
    };

    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;
        Serial.println("📱 Mobil app bağlantısı kesildi");
    }
};

// ==================== MAX30100 CALLBACK ====================
void onBeatDetected() {
    Serial.println("♥ Beat!");
}

// ==================== YARDIMCI FONKSİYONLAR ====================
float calculateAccMagnitude(float ax, float ay, float az) {
    return sqrtf(ax * ax + ay * ay + az * az);
}

void setLed(bool on) {
    if (LED_PIN >= 0) {
        digitalWrite(LED_PIN, on ? HIGH : LOW);
    }
}

bool checkButtonPress() {
    bool reading = digitalRead(BUTTON_PIN);
    
    if (reading != lastButtonState) {
        lastDebounceTime = millis();
    }
    
    if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
        static bool stableState = true;
        if (reading != stableState) {
            stableState = reading;
            if (reading == LOW) {
                return true;
            }
        }
    }
    
    lastButtonState = reading;
    return false;
}

String getStateString() {
    switch (currentState) {
        case NORMAL: return "NORMAL";
        case IMPACT_DETECTED: return "IMPACT";
        case FALL_ALARM: return "FALL_ALARM";
        case MANUAL_ALARM: return "MANUAL_ALARM";
        default: return "UNKNOWN";
    }
}

// ==================== BLE VERİ GÖNDERİMİ ====================
void sendSensorDataViaBLE() {
    if (!deviceConnected) return;
    
    char jsonBuffer[256];
    snprintf(jsonBuffer, sizeof(jsonBuffer),
        "{\"acc\":{\"x\":%.2f,\"y\":%.2f,\"z\":%.2f},"
        "\"gyro\":{\"x\":%.1f,\"y\":%.1f,\"z\":%.1f},"
        "\"ppg\":%d,"
        "\"hr\":%d,"
        "\"spo2\":%d,"
        "\"state\":\"%s\"}",
        accX, accY, accZ,
        gyroX, gyroY, gyroZ,
        (int)(heartRate * 100),
        heartRate,
        spO2,
        getStateString().c_str()
    );
    
    pSensorCharacteristic->setValue(jsonBuffer);
    pSensorCharacteristic->notify();
    
    Serial.print("📤 ");
    Serial.println(jsonBuffer);
}

void sendAlarmViaBLE(const char* alarmType) {
    if (!deviceConnected) return;
    
    char jsonBuffer[128];
    snprintf(jsonBuffer, sizeof(jsonBuffer),
        "{\"alarm\":\"%s\",\"ts\":%lu}",
        alarmType, millis()
    );
    
    pAlarmCharacteristic->setValue(jsonBuffer);
    pAlarmCharacteristic->notify();
    
    Serial.print("🚨 ");
    Serial.println(jsonBuffer);
}

// ==================== SENSÖR OKUMA ====================
void readMPU6050() {
    if (!mpuReady) return;
    
    sensors_event_t a, g, temp;
    mpu.getEvent(&a, &g, &temp);
    
    // m/s² → g
    accX = a.acceleration.x / 9.81f;
    accY = a.acceleration.y / 9.81f;
    accZ = a.acceleration.z / 9.81f;
    
    // rad/s → deg/s
    gyroX = g.gyro.x * 57.2958f;
    gyroY = g.gyro.y * 57.2958f;
    gyroZ = g.gyro.z * 57.2958f;
    
    accMagnitude = calculateAccMagnitude(accX, accY, accZ);
}

void readMAX30100() {
    if (!poxReady) return;
    pox.update();
    heartRate = pox.getHeartRate();
    spO2 = pox.getSpO2();
}

// ==================== DÜŞME TESPİT ====================
void checkFallDetection() {
    uint32_t now = millis();
    float aDeltaFrom1G = fabsf(accMagnitude - 1.0f);
    
    switch (currentState) {
        case NORMAL:
            setLed(false);
            if (accMagnitude >= FALL_PEAK_G) {
                impactTime = now;
                stillRunning = false;
                currentState = IMPACT_DETECTED;
                Serial.println("⚠️ Darbe!");
            }
            break;
            
        case IMPACT_DETECTED:
            if (aDeltaFrom1G <= STILL_DELTA_G) {
                if (!stillRunning) {
                    stillRunning = true;
                    stillStartTime = now;
                } else if (now - stillStartTime >= STILL_TIME_MS) {
                    currentState = FALL_ALARM;
                    Serial.println("🚨 DÜŞME!");
                    sendAlarmViaBLE("FALL");
                }
            } else {
                stillRunning = false;
            }
            
            if (now - impactTime > 10000) {
                currentState = NORMAL;
                stillRunning = false;
            }
            break;
            
        case FALL_ALARM:
        case MANUAL_ALARM:
            setLed(true);
            break;
    }
}

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n=== CDTP Health Monitor v1.0 ===\n");
    
    // I2C
    Wire.begin(SDA_PIN, SCL_PIN);
    
    // LED & Button
    if (LED_PIN >= 0) {
        pinMode(LED_PIN, OUTPUT);
        setLed(false);
    }
    pinMode(BUTTON_PIN, INPUT_PULLUP);
    
    // MPU6050
    Serial.print("MPU6050... ");
    if (mpu.begin()) {
        Serial.println("OK ✓");
        mpu.setAccelerometerRange(MPU6050_RANGE_2_G);
        mpu.setGyroRange(MPU6050_RANGE_250_DEG);
        mpu.setFilterBandwidth(MPU6050_BAND_21_HZ);
        mpuReady = true;
    } else {
        Serial.println("HATA ✗");
    }
    
    // MAX30100
    Serial.print("MAX30100... ");
    if (pox.begin()) {
        Serial.println("OK ✓");
        pox.setOnBeatDetectedCallback(onBeatDetected);
        pox.setIRLedCurrent(MAX30100_LED_CURR_7_6MA);
        poxReady = true;
    } else {
        Serial.println("YOK (nabız çalışmaz)");
    }
    
    // BLE
    Serial.print("BLE... ");
    BLEDevice::init(DEVICE_NAME);
    
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());
    
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    pSensorCharacteristic = pService->createCharacteristic(
        SENSOR_CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    pSensorCharacteristic->addDescriptor(new BLE2902());
    
    pAlarmCharacteristic = pService->createCharacteristic(
        ALARM_CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );
    pAlarmCharacteristic->addDescriptor(new BLE2902());
    
    pService->start();
    
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->start();
    
    Serial.println("OK ✓");
    Serial.println("\n📡 BLE: CDTP-Watch");
    Serial.println("📱 Bağlantı bekleniyor...\n");
}

// ==================== LOOP ====================
void loop() {
    uint32_t now = millis();
    
    // 1) MAX30100 Update (EN ÖNEMLİ: Her döngüde çağrılmalı)
    if (poxReady) {
        pox.update();
    }
    
    // 2) Sensör Verilerini Periyodik Olarak Al
    if (now - lastPpgSample >= PPG_SAMPLE_PERIOD_MS) {
        if (poxReady) {
            heartRate = pox.getHeartRate();
            spO2 = pox.getSpO2();
        }
        lastPpgSample = now;
    }
    
    // 3) Buton Kontrolü
    if (checkButtonPress()) {
        currentState = MANUAL_ALARM;
        stillRunning = false;
        Serial.println("🚨 BUTON!");
        sendAlarmViaBLE("MANUAL");
    }
    
    // 4) MPU6050 + Düşme Tespiti
    if (now - lastSensorRead >= SENSOR_PERIOD_MS) {
        readMPU6050();
        checkFallDetection();
        lastSensorRead = now;
    }
    
    // 5) BLE Notify
    if (now - lastBleNotify >= BLE_NOTIFY_PERIOD_MS) {
        sendSensorDataViaBLE();
        lastBleNotify = now;
    }
    
    // 6) Reconnect Logic
    if (!deviceConnected && oldDeviceConnected) {
        delay(500); // Bağlantı koptuğunda kısa bekleme
        pServer->startAdvertising();
        oldDeviceConnected = deviceConnected;
        Serial.println("📡 Re-advertising...");
    }
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
    }
    
    // 7) Serial Reset
    if (Serial.available()) {
        char c = Serial.read();
        if (c == 'r' || c == 'R') {
            currentState = NORMAL;
            stillRunning = false;
            setLed(false);
            Serial.println("✅ Reset");
        }
    }
    
    // Delay yok veya çok kısa (MAX30100 için)
    // delay(10); // KALDIRILDI
}
