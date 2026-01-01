#include <WiFi.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>     
#include <Wire.h>
#include <MPU6050.h>
#include <time.h>





struct EspDataDTO {
  const char* deviceId;
  String timeStamp;     // 👈 DÜZELTİLDİ
  long  seq;

  float ax;
  float ay;
  float az;
  float gx;
  float gy;
  float gz;

  int   hr;
  bool  manualAlarm;
};

// -------------- SENSORLER ------------

bool mpuReady = false;
unsigned long lastMpuRetryMs = 0;
const unsigned long MPU_RETRY_INTERVAL_MS = 3000; // 3 sn


//-------IVME , KONUM -------
#define SDA_PIN 21
#define SCL_PIN 22

MPU6050 mpu;

bool initMPU6050() {
  Wire.begin(SDA_PIN, SCL_PIN);
  Wire.setClock(400000);

  mpu.initialize();

  if (!mpu.testConnection()) {
    Serial.println("MPU6050 BAGLANTI YOK ❌");
    return false;
  }

  Serial.println("MPU6050 BAGLANTI OK ✅");
  return true;
}


void readMPU6050(EspDataDTO& d) {
  if (!mpuReady) return;

  int16_t ax_r, ay_r, az_r;
  int16_t gx_r, gy_r, gz_r;

  if (!mpu.testConnection()) {
    Serial.println("MPU6050 KOPTU ⚠️");
    mpuReady = false;
    return;
  }

  mpu.getAcceleration(&ax_r, &ay_r, &az_r);
  mpu.getRotation(&gx_r, &gy_r, &gz_r);

  d.ax = ax_r / 16384.0f;
  d.ay = ay_r / 16384.0f;
  d.az = az_r / 16384.0f;

  d.gx = gx_r / 131.0f;
  d.gy = gy_r / 131.0f;
  d.gz = gz_r / 131.0f;
}







//-------WEB,BACKEND,JSON,HTTP-----------------

String espDataToJson(const EspDataDTO& d, bool pretty = false) {
  StaticJsonDocument<384> doc;

  doc["deviceId"]    = d.deviceId;
  doc["timeStamp"]   = d.timeStamp;
  doc["seq"]         = d.seq;

  doc["ax"] = d.ax;
  doc["ay"] = d.ay;
  doc["az"] = d.az;
  doc["gx"] = d.gx;
  doc["gy"] = d.gy;
  doc["gz"] = d.gz;

  doc["hr"]          = d.hr;
  doc["manualAlarm"] = d.manualAlarm;

  String out;
  pretty ? serializeJsonPretty(doc, out)
         : serializeJson(doc, out);

  return out;
}

EspDataDTO makeEspDataFromSensors() {
  EspDataDTO d;

  d.deviceId    = "ESP-001";
  d.timeStamp = getIsoTimestampUTC(); 
  d.seq         = millis();

  readMPU6050(d);   


  d.hr          = 78;
  d.manualAlarm = false;

  return d;
}

String getIsoTimestampUTC() {
  time_t now = time(nullptr);
  struct tm tm;
  gmtime_r(&now, &tm);

  char buf[25];
  strftime(buf, sizeof(buf), "%Y-%m-%dT%H:%M:%SZ", &tm);
  return String(buf);
}



void initTime() {
  configTime(
    0,              // GMT offset (UTC için 0)
    0,              // daylight offset
    "pool.ntp.org",
    "time.nist.gov"
  );

  Serial.print("NTP zamani aliniyor");
  time_t now;
  while ((now = time(nullptr)) < 100000) {
    Serial.print(".");
    delay(500);
  }
  Serial.println(" OK ✅");
}


const char* HOST = "172.20.10.4";     // makinenizin LAN IP'si
const uint16_t PORT = 8080;           // Spring Boot portu
const char* PATH = "/api/esp";

bool postTelemetry(const EspDataDTO& d) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WIFI YOK POST ATLANIYOR");
    return false;
  }

  String url = String("http://") + HOST + ":" + PORT + PATH;
  String body = espDataToJson(d);

  HTTPClient http;
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  Serial.println("POST URL : " + url);
  Serial.println("POST JSON:");
  Serial.println(body);

  int code = http.POST(body);
  Serial.print("HTTP CODE = ");
  Serial.println(code);

  http.end();
  return (code >= 200 && code < 300);
}



// ---- WIFI ----
const char* WIFI_SSID = "Izzet-Iphone";
const char* WIFI_PASS = "123456789";

// Kaç ms içinde bağlanamazsa vazgeçsin?
const uint32_t WIFI_TIMEOUT_MS = 20000; // 20 sn

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.persistent(false);         
  WiFi.setAutoReconnect(true);     
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  Serial.print("WiFi'ya baglaniyor");
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < WIFI_TIMEOUT_MS) {
    Serial.print(".");
    delay(250);
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi BAGLANTI TAMAM ✅");
    Serial.print("IP: ");   Serial.println(WiFi.localIP());
    Serial.print("RSSI: "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  } else {
    Serial.println("WiFi BAGLANAMADI ❌ (SSID/sifre/kapsama kontrol et)");
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);

  connectWiFi();
  initTime();

  mpuReady = initMPU6050(); // ilk deneme
}



unsigned long lastPostMs = 0;
const unsigned long POST_PERIOD_MS = 2000; 

void loop() {
  unsigned long now = millis();

  // 🔁 MPU6050 reconnect logic
  if (!mpuReady && now - lastMpuRetryMs >= MPU_RETRY_INTERVAL_MS) {
    lastMpuRetryMs = now;
    Serial.println("MPU6050 tekrar baglaniliyor...");
    mpuReady = initMPU6050();
  }

  // 📤 POST only if MPU hazır
  if (mpuReady && now - lastPostMs >= POST_PERIOD_MS) {
    lastPostMs = now;

    EspDataDTO dto = makeEspDataFromSensors();
    postTelemetry(dto);
  }

  delay(50);
}


