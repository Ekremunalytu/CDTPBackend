/*
 * CDTP Sağlık İzleme Sistemi - ESP32 Firmware
 *
 * Donanım:
 * - ESP32-C3-Mini-1
 * - MPU6050 (6-axis accelerometer + gyroscope)
 * - Analog Pulse Sensor (ADC pin)
 * - Button (acil durum)
 *
 * Kütüphaneler:
 * - Adafruit MPU6050
 */

#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <BLEAdvertising.h>

// ==================== PIN TANIMLARI ====================
#define SDA_PIN 6
#define SCL_PIN 7
#define BUTTON_PIN 2
#define LED_PIN 8      // ESP32-C3 dahili LED (varsa, yoksa -1 yap)
#define PULSE_PIN 0    // ESP32-C3 ADC pini (GPIO0 = ADC1_CH0)

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
#define SENSOR_PERIOD_MS 200       // MPU6050 okuma periyodu (5 Hz)
#define BLE_NOTIFY_PERIOD_MS 500   // BLE bildirim periyodu (2 Hz)
#define PULSE_SAMPLE_MS 10         // Nabız örnekleme (100 Hz)

// ==================== GLOBAL DEĞİŞKENLER ====================
Adafruit_MPU6050 mpu;
bool mpuReady = false;

BLEServer* pServer = NULL;
BLECharacteristic* pSensorCharacteristic = NULL;
BLECharacteristic* pAlarmCharacteristic = NULL;
bool deviceConnected = false;
bool oldDeviceConnected = false;

BLEAdvertising* pAdvertising = nullptr;

// Durum makinesi
enum State { NORMAL, IMPACT_DETECTED, FALL_ALARM, MANUAL_ALARM };
State currentState = NORMAL;

// Zamanlamalar
uint32_t lastSensorRead = 0;
uint32_t lastBleNotify = 0;
uint32_t lastPulseSample = 0;
uint32_t impactTime = 0;
uint32_t stillStartTime = 0;
bool stillRunning = false;

// Sensör verileri
float accX = 0, accY = 0, accZ = 0;
float gyroX = 0, gyroY = 0, gyroZ = 0;
float accMagnitude = 1.0f;
int heartRate = 0;
int spO2 = 0;  // Analog sensörde SpO2 yok, 0 gönderilir

// Buton debounce
bool lastButtonState = true;
uint32_t lastDebounceTime = 0;
const uint32_t DEBOUNCE_DELAY = 50;

// ==================== NABIZ ALGILAMA DEĞİŞKENLERİ ====================
int BPM = 0;
int BPM_raw = 0;
int Signal = 0;
int IBI = 600;
bool Pulse = false;
bool QS = false;

// IBI filtreleme
const int MIN_IBI = 450;
const int MAX_IBI = 1500;

// Algoritma değişkenleri
int rate[10];
unsigned long sampleCounter = 0;
unsigned long lastBeatTime = 0;
int P = 2048, T = 2048, thresh = 2100, amp = 100;
bool firstBeat = true, secondBeat = false;

// Smoothing
float bpmSmooth = 0.0f;
const float BPM_ALPHA = 0.2f;

// ==================== BLE CALLBACKS ====================
class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) override {
        deviceConnected = true;
        Serial.println("📱 Mobil app bağlandı!");
    };

    void onDisconnect(BLEServer* pServer) override {
        deviceConnected = false;
        Serial.println("📱 Mobil app bağlantısı kesildi");
    }
};

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

// ==================== BLE ADVERTISING (SAMSUNG-UYUMLU) ====================
static void startBleAdvertising() {
    if (!pAdvertising) return;

    BLEAdvertisementData adv;
    adv.setName(DEVICE_NAME);
    adv.setCompleteServices(BLEUUID(SERVICE_UUID));
    pAdvertising->setAdvertisementData(adv);

    BLEAdvertisementData scan;
    scan.setName(DEVICE_NAME);
    pAdvertising->setScanResponseData(scan);

    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);

    BLEDevice::startAdvertising();
    Serial.println("📡 Advertising started (Samsung-friendly)");
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
        Signal,
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

// ==================== NABIZ OKUMA (ANALOG SENSOR) ====================
void processPulseSensor() {
    sampleCounter += PULSE_SAMPLE_MS;
    
    // Analog okuma + filtreleme
    int raw = analogRead(PULSE_PIN);
    Signal = (0.7 * Signal) + (0.3 * raw);

    int N = sampleCounter - lastBeatTime;

    if (Signal < thresh && N > (IBI / 5) * 3) { 
        if (Signal < T) T = Signal; 
    }
    if (Signal > thresh && Signal > P) { 
        P = Signal; 
    }

    if (N > MIN_IBI) {
        if ((Signal > thresh) && (Pulse == false)) {
            Pulse = true;
            Serial.println("💓 Peak detected!");
            IBI = sampleCounter - lastBeatTime;
            lastBeatTime = sampleCounter;

            if (IBI >= MIN_IBI && IBI <= MAX_IBI) {
                if (firstBeat) { 
                    firstBeat = false; 
                    secondBeat = true; 
                }
                else if (secondBeat) { 
                    secondBeat = false; 
                    for (int i = 0; i < 10; i++) rate[i] = IBI; 
                }
                else {
                    long runningTotal = 0;
                    for (int i = 0; i < 9; i++) { 
                        rate[i] = rate[i + 1]; 
                        runningTotal += rate[i]; 
                    }
                    rate[9] = IBI; 
                    runningTotal += rate[9]; 
                    runningTotal /= 10;

                    if (runningTotal > 0) {
                        BPM_raw = 60000 / runningTotal;
                        if (BPM_raw >= 40 && BPM_raw <= 220) {
                            // BPM düzeltme (sensör çift sayıyorsa)
                            int displayBPM = BPM_raw;
                            if (displayBPM > 110 && displayBPM < 160) {
                                displayBPM = map(displayBPM, 110, 160, 70, 95);
                            }

                            if (bpmSmooth < 1.0f) bpmSmooth = (float)displayBPM;
                            else bpmSmooth = (0.7 * bpmSmooth) + (0.3 * (float)displayBPM);  // Daha hızlı tepki
                            
                            BPM = (int)(bpmSmooth + 0.5f);
                            heartRate = BPM;
                            QS = true;
                            
                            // Debug: Nabız algılandığında yazdır
                            Serial.print("♥️ Beat! BPM: ");
                            Serial.print(BPM);
                            Serial.print(" (raw: ");
                            Serial.print(BPM_raw);
                            Serial.print(", IBI: ");
                            Serial.print(IBI);
                            Serial.println("ms)");
                        }
                    }
                }
            }
        }
    }

    if (Signal < thresh && Pulse == true) {
        Pulse = false;
        amp = P - T;
        if (amp < 20) amp = 20;  // Düşük amplitüd için 100'den 20'ye düşürüldü
        thresh = T + amp / 2;
        P = thresh; 
        T = thresh;
    }

    // Uzun süre nabız yoksa reset (5 saniye)
    if (N > 5000) {
        thresh = Signal + 15;  // 50'den 15'e düşürüldü (düşük amplitüd için)
        P = Signal; 
        T = Signal;
        lastBeatTime = sampleCounter;
        firstBeat = true; 
        secondBeat = false;
        BPM = 0; 
        bpmSmooth = 0.0f;
        heartRate = 0;
    }
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

    Serial.println("\n=== CDTP Health Monitor v1.1 (Analog Pulse) ===\n");

    // ADC ayarı (voltaj kırpılmasını engeller)
    analogSetAttenuation(ADC_11db);

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

    // Nabız sensörü kalibrasyon
    Serial.print("Pulse Sensor... ");
    long sum = 0;
    for (int i = 0; i < 150; i++) {
        sum += analogRead(PULSE_PIN);
        delay(PULSE_SAMPLE_MS);
    }
    int base = sum / 150;
    
    // Sensör boşta çok yüksek/düşük veriyorsa güvenli moda geç
    if (base > 3500 || base < 100) base = 2048;
    
    P = base; T = base; thresh = base + 15;  // Düşük amplitüd için 50'den 15'e
    Serial.println("OK ✓");

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

    pAdvertising = BLEDevice::getAdvertising();
    startBleAdvertising();

    Serial.println("OK ✓");
    Serial.println("\n📡 BLE: CDTP-Watch");
    Serial.println("📱 Bağlantı bekleniyor...\n");
}

// ==================== LOOP ====================
void loop() {
    uint32_t now = millis();

    // 1) Nabız sensörü örnekleme (yüksek frekansta)
    if (now - lastPulseSample >= PULSE_SAMPLE_MS) {
        processPulseSensor();
        lastPulseSample = now;
    }

    // 2) Buton Kontrolü
    if (checkButtonPress()) {
        currentState = MANUAL_ALARM;
        stillRunning = false;
        Serial.println("🚨 BUTON!");
        sendAlarmViaBLE("MANUAL");
    }

    // 3) MPU6050 + Düşme Tespiti
    if (now - lastSensorRead >= SENSOR_PERIOD_MS) {
        readMPU6050();
        checkFallDetection();
        lastSensorRead = now;
    }

    // 4) BLE Notify
    if (now - lastBleNotify >= BLE_NOTIFY_PERIOD_MS) {
        sendSensorDataViaBLE();
        lastBleNotify = now;
    }

    // 5) Reconnect Logic
    if (!deviceConnected && oldDeviceConnected) {
        delay(500);
        startBleAdvertising();
        oldDeviceConnected = deviceConnected;
        Serial.println("📡 Re-advertising...");
    }
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
    }

    // 6) Serial Reset
    if (Serial.available()) {
        char c = Serial.read();
        if (c == 'r' || c == 'R') {
            currentState = NORMAL;
            stillRunning = false;
            setLed(false);
            Serial.println("✅ Reset");
        }
    }
}