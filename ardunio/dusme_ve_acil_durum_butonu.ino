#include <Wire.h>
#include <MPU6050.h>
#include <math.h>

// -------------------- PINLER --------------------
#define SDA_PIN 6
#define SCL_PIN 7

const int BUTTON_PIN = 2;  // Buton: GPIO13 -> GND (INPUT_PULLUP)
const int LED_PIN = -1;     // LED yoksa -1. Örn: 14 yaparsan LED kontrol eder

// -------------------- ZAMANLAMALAR --------------------
#define REPORTING_PERIOD_MS 200  // ekrana yazma periyodu (ms)

// -------------------- DÜŞME EŞİKLERİ --------------------
const float FALL_PEAK_G = 2.5f;          // ani darbe eşiği (g)
const uint32_t STILL_TIME_MS = 5000;     // darbeden sonra hareketsizlik süresi (ms)
const float STILL_DELTA_G = 0.08f;       // |a|-1g toleransı (g)

// -------------------- GLOBAL --------------------
MPU6050 mpu;
uint32_t tsLastReport = 0;

// Durumlar
enum State { NORMAL, IMPACT_DETECTED, FALL_ALARM, MANUAL_ALARM };
State state = NORMAL;

uint32_t impactTime = 0;
uint32_t stillStartTime = 0;
bool stillRunning = false;

// Buton debounce
bool lastButtonReading = true; // pullup: basılı değilken HIGH(true)
uint32_t lastDebounceMs = 0;
const uint32_t DEBOUNCE_MS = 40;

// -------------------- YARDIMCI --------------------
static inline float accelMagnitudeG(float ax, float ay, float az) {
  return sqrtf(ax * ax + ay * ay + az * az);
}

static inline void setLed(bool on) {
  if (LED_PIN >= 0) digitalWrite(LED_PIN, on ? HIGH : LOW);
}

bool buttonPressedEvent(uint32_t now) {
  // INPUT_PULLUP: basınca LOW olur
  bool reading = digitalRead(BUTTON_PIN);

  if (reading != lastButtonReading) {
    lastDebounceMs = now;
    lastButtonReading = reading;
  }

  if ((now - lastDebounceMs) > DEBOUNCE_MS) {
    // Stabil olarak LOW ise "basıldı" olayı üretelim (edge)
    static bool lastStable = true;
    if (reading != lastStable) {
      lastStable = reading;
      if (reading == false) { // LOW
        return true;
      }
    }
  }
  return false;
}

// -------------------- SETUP --------------------
void setup() {
  Serial.begin(115200);
  delay(800);

  Serial.println();
  Serial.println("ESP32 + MPU6050 (DUSME + BUTON) baslatiliyor...");

  // I2C
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(100000);

  // MPU6050
  mpu.initialize();
  if (!mpu.testConnection()) {
    Serial.println("MPU6050 FAILED (baglanti / besleme / I2C kontrol et)");
    while (1) delay(1000);
  }
  Serial.println("MPU6050 OK");

  // Buton
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // LED
  if (LED_PIN >= 0) {
    pinMode(LED_PIN, OUTPUT);
    setLed(false);
  }

  Serial.println("Buton: GPIO13 -> GND (INPUT_PULLUP). Basinca MANUAL ALARM.");
  Serial.println("Resetlemek icin Serial'a 'r' gonderebilirsin.");
  Serial.println("Düşme: |a|>2.5g => impact, sonra 5sn abs(|a|-1g)<0.08 => FALL ALARM");
}

// -------------------- LOOP --------------------
void loop() {
  uint32_t now = millis();

  // 1) Buton basıldı mı? (her zaman en öncelikli)
  if (buttonPressedEvent(now)) {
    state = MANUAL_ALARM;
    stillRunning = false;
    Serial.println("!!! MANUEL ALARM: Butona basildi.");
  }

  // 2) MPU verileri oku
  int16_t ax_raw, ay_raw, az_raw;
  int16_t gx_raw, gy_raw, gz_raw;

  mpu.getAcceleration(&ax_raw, &ay_raw, &az_raw);
  mpu.getRotation(&gx_raw, &gy_raw, &gz_raw);

  float ax = ax_raw / 16384.0f;
  float ay = ay_raw / 16384.0f;
  float az = az_raw / 16384.0f;

  float gx = gx_raw / 131.0f;
  float gy = gy_raw / 131.0f;
  float gz = gz_raw / 131.0f;

  float aMag = accelMagnitudeG(ax, ay, az);
  float aDeltaFrom1G = fabsf(aMag - 1.0f);

  // 3) Durum makinesi
  switch (state) {
    case NORMAL: {
      setLed(false);
      if (aMag >= FALL_PEAK_G) {
        impactTime = now;
        stillRunning = false;
        state = IMPACT_DETECTED;
        Serial.println(">> Darbe algilandi (impact). Hareketsizlik kontrolu basliyor...");
      }
      break;
    }

    case IMPACT_DETECTED: {
      setLed(false);

      bool isStill = (aDeltaFrom1G <= STILL_DELTA_G);

      if (isStill) {
        if (!stillRunning) {
          stillRunning = true;
          stillStartTime = now;
        } else if (now - stillStartTime >= STILL_TIME_MS) {
          state = FALL_ALARM;
          Serial.println("!!! DUSME ALARMI: Darbe + uzun hareketsizlik tespit edildi.");
        }
      } else {
        stillRunning = false;
      }

      if (now - impactTime > 10000) {
        state = NORMAL;
        stillRunning = false;
        Serial.println(">> Darbe sonlandi, normale donuldu (alarm yok).");
      }
      break;
    }

    case FALL_ALARM: {
      setLed(true);
      static uint32_t lastAlarmPrint = 0;
      if (now - lastAlarmPrint > 2000) {
        Serial.println("!!! FALL ALARM AKTIF (reset icin 'r')");
        lastAlarmPrint = now;
      }
      break;
    }

    case MANUAL_ALARM: {
      setLed(true);
      static uint32_t lastManualPrint = 0;
      if (now - lastManualPrint > 2000) {
        Serial.println("!!! MANUAL ALARM AKTIF (reset icin 'r')");
        lastManualPrint = now;
      }
      break;
    }
  }

  // 4) Reset komutu (alarmdan çık)
  if (Serial.available()) {
    char c = (char)Serial.read();
    if (c == 'r' || c == 'R') {
      state = NORMAL;
      stillRunning = false;
      setLed(false);
      Serial.println(">> Alarm resetlendi, NORMAL moda donuldu.");
    }
  }

  // 5) Log
  if (now - tsLastReport >= REPORTING_PERIOD_MS) {
    Serial.print("State=");
    Serial.print((state == NORMAL) ? "NORMAL" :
                 (state == IMPACT_DETECTED) ? "IMPACT" :
                 (state == FALL_ALARM) ? "FALL_ALARM" : "MANUAL_ALARM");

    Serial.print(" | |a|=");
    Serial.print(aMag, 2);
    Serial.print("g");

    Serial.print(" | d(|a|-1g)=");
    Serial.print(aDeltaFrom1G, 2);

    Serial.print(" | Acc(g) X=");
    Serial.print(ax, 2);
    Serial.print(" Y=");
    Serial.print(ay, 2);
    Serial.print(" Z=");
    Serial.print(az, 2);

    Serial.print(" | Gyro(dps) X=");
    Serial.print(gx, 1);
    Serial.print(" Y=");
    Serial.print(gy, 1);
    Serial.print(" Z=");
    Serial.println(gz, 1);

    tsLastReport = now;
  }

  delay(10);
}

