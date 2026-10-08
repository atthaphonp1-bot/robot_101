// Robot Arm 6DOF firmware (ESP32) — same JSON protocol as sim/index.html
// Wokwi: USE_PCA9685 0 (servos on GPIO).  Real board with PCA9685: USE_PCA9685 1
#include <Arduino.h>
#include <WiFi.h>
#include <Wire.h>
#include <ArduinoJson.h>
#include <WebSocketsServer.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define USE_PCA9685 0

#if USE_PCA9685
#include <Adafruit_PWMServoDriver.h>
Adafruit_PWMServoDriver pca(0x40);
#else
#include <ESP32Servo.h>
Servo servos[6];
const int SERVO_PINS[6] = {13, 12, 14, 27, 26, 25};
#endif

// ---- config -----------------------------------------------------------------
const char* WIFI_SSID = "Wokwi-GUEST";   // change for real router
const char* WIFI_PASS = "";
const char* AP_SSID = "RobotArm";        // fallback access point -> 192.168.4.1
const char* AP_PASS = "robot1234";
const int ESTOP_PIN = 4;                 // button to GND, toggles E-stop

// ---- MQTT: control over the internet ----------------------------------------
#define USE_MQTT 1
#define MQTT_TLS 0                         // 1 = TLS (HiveMQ Cloud port 8883)
const char* MQTT_HOST = "broker.hivemq.com"; // public test broker: anyone can publish, use a unique prefix
const int MQTT_PORT = 1883;
const char* MQTT_USER = "";
const char* MQTT_PASS = "";
const char* MQTT_PREFIX = "robot101/arm1"; // topics: <prefix>/cmd, /state, /status, /reply

// joint angle = (servo - offset) * dir  — same table as the simulator
struct Joint { const char* key; float minA, maxA, home, offset, dir; };
Joint J[6] = {
  {"J1", 0, 180, 90, 90, 1},    // base
  {"J2", 15, 165, 90, 90, 1},   // shoulder
  {"J3", 0, 180, 135, 45, 1},   // elbow
  {"J4", 0, 180, 135, 90, 1},   // wrist pitch
  {"J5", 0, 180, 90, 90, 1},    // wrist roll
  {"J6", 10, 120, 80, 0, 1},    // gripper
};
const float L_BASE = 95, L_UPPER = 120, L_FORE = 115, TCP = 95;   // mm

// ---- state ------------------------------------------------------------------
float cur[6], tgt[6], spd[6];
float speedDps = 90;
bool estop = false;
WebSocketsServer ws(81);
Adafruit_SSD1306 oled(128, 64, &Wire, -1);
bool oledOk = false;

// ---- servo output -------------------------------------------------------------
void writeServo(int i, float deg) {
  int us = 500 + (int)(deg / 180.0f * 2000.0f);
#if USE_PCA9685
  pca.writeMicroseconds(i, us);
#else
  servos[i].writeMicroseconds(us);
#endif
}

// synchronized move: all arm joints arrive together (gripper independent)
void setTargets(const float a[6]) {
  float mx = 0;
  for (int i = 0; i < 6; i++) tgt[i] = constrain(a[i], J[i].minA, J[i].maxA);
  for (int i = 0; i < 5; i++) mx = max(mx, fabsf(tgt[i] - cur[i]));
  for (int i = 0; i < 5; i++) spd[i] = mx > 0.01f ? max(1.0f, speedDps * fabsf(tgt[i] - cur[i]) / mx) : speedDps;
  spd[5] = speedDps * 1.5f;
}

// ---- inverse kinematics (identical math to the simulator) ---------------------
bool solveIK(float x, float y, float z, float pitch, float out[4]) {
  float yaw = degrees(atan2f(y, x)), r = hypotf(x, y);
  if (yaw < -90 || yaw > 90) { yaw += yaw > 0 ? -180 : 180; r = -r; }
  float phi4 = radians(r < 0 ? pitch - 90 : 90 - pitch);
  float rw = r - TCP * sinf(phi4), zw = z - L_BASE - TCP * cosf(phi4);
  float c = (rw * rw + zw * zw - L_UPPER * L_UPPER - L_FORE * L_FORE) / (2 * L_UPPER * L_FORE);
  if (fabsf(c) > 1) return false;
  float a = acosf(c);
  float cands[2] = {r < 0 ? -a : a, r < 0 ? a : -a};
  for (float t3 : cands) {
    float t2 = atan2f(rw, zw) - atan2f(L_FORE * sinf(t3), L_UPPER + L_FORE * cosf(t3));
    float t4 = degrees(phi4 - t2 - t3);
    t4 = fmodf(fmodf(t4 + 180, 360) + 360, 360) - 180;
    float th[4] = {yaw, degrees(t2), degrees(t3), t4};
    bool ok = true;
    for (int i = 0; i < 4; i++) {
      out[i] = J[i].offset + th[i] / J[i].dir;
      if (out[i] < J[i].minA || out[i] > J[i].maxA) ok = false;
    }
    if (ok) return true;
  }
  return false;
}
bool autoIK(float x, float y, float z, float pitch, float out[4]) {
  for (int d = 0; d <= 180; d += 5)
    for (int s = 0; s < (d ? 2 : 1); s++) {
      float p = pitch + (s ? -d : d);
      if (p >= -90 && p <= 90 && solveIK(x, y, z, p, out)) return true;
    }
  return false;
}

// ---- command protocol ---------------------------------------------------------
// {"j":[6]} {"ik":[x,y,z,pitch]} {"grip":v} {"speed":v} {"home":1} {"stop":1}
String handleCommand(const char* txt) {
  JsonDocument d;
  if (deserializeJson(d, txt)) return "{\"err\":\"bad json\"}";
  if (d["stop"].is<int>()) { setTargets(cur); return "{\"ok\":\"stop\"}"; }
  if (d["speed"].is<float>()) { speedDps = constrain(d["speed"].as<float>(), 10, 360); return "{\"ok\":\"speed\"}"; }
  if (estop) return "{\"err\":\"estop\"}";

  float a[6];
  memcpy(a, tgt, sizeof a);
  if (d["j"].is<JsonArray>()) {
    JsonArray j = d["j"];
    for (int i = 0; i < 6 && i < (int)j.size(); i++) if (j[i].is<float>()) a[i] = j[i];
  } else if (d["ik"].is<JsonArray>()) {
    JsonArray k = d["ik"];
    float o[4];
    float pitch = k.size() > 3 ? k[3].as<float>() : -90;
    if (!autoIK(k[0], k[1], k[2], pitch, o)) return "{\"err\":\"unreachable\"}";
    memcpy(a, o, sizeof o);
  } else if (d["grip"].is<float>()) {
    a[5] = d["grip"];
  } else if (d["home"].is<int>()) {
    for (int i = 0; i < 6; i++) a[i] = J[i].home;
  } else {
    return "{\"err\":\"unknown\"}";
  }
  setTargets(a);
  return "";
}

void onWs(uint8_t num, WStype_t type, uint8_t* payload, size_t len) {
  if (type == WStype_TEXT) {
    String reply = handleCommand((const char*)payload);
    if (reply.length()) ws.sendTXT(num, reply);
  } else if (type == WStype_CONNECTED) {
    Serial.printf("WS client %u connected\n", num);
  }
}

// ---- MQTT -------------------------------------------------------------------
#if USE_MQTT
#include <PubSubClient.h>
#if MQTT_TLS
#include <WiFiClientSecure.h>
WiFiClientSecure mqttNet;
#else
WiFiClient mqttNet;
#endif
PubSubClient mqtt(mqttNet);
String topic(const char* leaf) { return String(MQTT_PREFIX) + "/" + leaf; }

void onMqtt(char* t, byte* payload, unsigned int len) {
  String msg;
  msg.reserve(len);
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  String reply = handleCommand(msg.c_str());
  if (reply.length()) mqtt.publish(topic("reply").c_str(), reply.c_str());
}

void mqttLoop() {
  if (WiFi.status() != WL_CONNECTED) return;   // AP fallback = no internet
  if (mqtt.connected()) { mqtt.loop(); return; }
  static uint32_t lastTry = 0;
  if (lastTry && millis() - lastTry < 3000) return;
  lastTry = millis();
  String id = "arm-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  String st = topic("status");
  if (mqtt.connect(id.c_str(), *MQTT_USER ? MQTT_USER : nullptr, *MQTT_PASS ? MQTT_PASS : nullptr,
                   st.c_str(), 1, true, "offline")) {          // last will: offline (retained)
    mqtt.publish(st.c_str(), "online", true);
    mqtt.subscribe(topic("cmd").c_str());
    Serial.printf("MQTT connected: %s/cmd\n", MQTT_PREFIX);
  } else {
    Serial.printf("MQTT failed rc=%d\n", mqtt.state());
  }
}
#endif

// ---- display ------------------------------------------------------------------
void drawOled() {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.println(WiFi.getMode() == WIFI_AP ? WiFi.softAPIP() : WiFi.localIP());
  oled.printf("J1 %3.0f J2 %3.0f J3 %3.0f\n", cur[0], cur[1], cur[2]);
  oled.printf("J4 %3.0f J5 %3.0f G  %3.0f\n", cur[3], cur[4], cur[5]);
  oled.printf("spd %.0f  ws %u\n", speedDps, ws.connectedClients());
  if (estop) { oled.setTextSize(2); oled.println("E-STOP"); oled.setTextSize(1); }
  oled.display();
}

// ---- setup / loop -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(ESTOP_PIN, INPUT_PULLUP);
  Wire.begin(21, 22);

#if USE_PCA9685
  pca.begin();
  pca.setOscillatorFrequency(27000000);
  pca.setPWMFreq(50);
#else
  for (int i = 0; i < 6; i++) servos[i].attach(SERVO_PINS[i], 500, 2500);
#endif
  for (int i = 0; i < 6; i++) { cur[i] = tgt[i] = J[i].home; spd[i] = speedDps; writeServo(i, cur[i]); }

  oledOk = oled.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  if (oledOk) { oled.setTextColor(SSD1306_WHITE); oled.setTextSize(1); }

  if (strcmp(WIFI_SSID, "Wokwi-GUEST") == 0) WiFi.begin(WIFI_SSID, WIFI_PASS, 6);   // channel 6 = fast in Wokwi
  else WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi");
  for (uint32_t t = millis(); WiFi.status() != WL_CONNECTED && millis() - t < 10000;) { delay(250); Serial.print('.'); }
  if (WiFi.status() == WL_CONNECTED) Serial.printf("\nIP: %s\n", WiFi.localIP().toString().c_str());
  else { WiFi.softAP(AP_SSID, AP_PASS); Serial.printf("\nAP %s  IP: %s\n", AP_SSID, WiFi.softAPIP().toString().c_str()); }

  ws.begin();
  ws.onEvent(onWs);
#if USE_MQTT
#if MQTT_TLS
  mqttNet.setInsecure();   // demo only: skips certificate check, load the broker CA for real use
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqtt);
  mqtt.setBufferSize(512);
#endif
  Serial.println("Ready. Send JSON per line, e.g. {\"ik\":[180,0,60,-90]}");
}

void loop() {
  ws.loop();
#if USE_MQTT
  mqttLoop();
#endif

  // serial: one JSON command per line
  static String line;
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (line.length()) { String r = handleCommand(line.c_str()); Serial.println(r.length() ? r : "{\"ok\":1}"); line = ""; }
    } else line += ch;
  }

  // E-stop toggle (debounced falling edge)
  static bool lastBtn = HIGH;
  static uint32_t btnT = 0;
  bool b = digitalRead(ESTOP_PIN);
  if (b != lastBtn && millis() - btnT > 50) {
    btnT = millis();
    lastBtn = b;
    if (b == LOW) { estop = !estop; setTargets(cur); Serial.println(estop ? "E-STOP ON" : "E-STOP OFF"); }
  }

  // motion @ 50 Hz
  static uint32_t lastMove = millis();
  uint32_t now = millis();
  if (now - lastMove >= 20) {
    float dt = (now - lastMove) / 1000.0f;
    lastMove = now;
    if (!estop)
      for (int i = 0; i < 6; i++) {
        float d = tgt[i] - cur[i], m = spd[i] * dt;
        cur[i] += fabsf(d) <= m ? d : (d > 0 ? m : -m);
        writeServo(i, cur[i]);
      }
  }

  // state broadcast @ 10 Hz, display @ 5 Hz
  static uint32_t lastState = 0, lastOled = 0;
  if (now - lastState >= 100) {
    lastState = now;
    bool moving = false;
    for (int i = 0; i < 6; i++) if (fabsf(tgt[i] - cur[i]) > 0.5f) moving = true;
    char buf[128];
    snprintf(buf, sizeof buf, "{\"state\":[%.0f,%.0f,%.0f,%.0f,%.0f,%.0f],\"moving\":%s,\"estop\":%s}",
             cur[0], cur[1], cur[2], cur[3], cur[4], cur[5], moving ? "true" : "false", estop ? "true" : "false");
    ws.broadcastTXT(buf);
#if USE_MQTT
    static uint32_t lastPub = 0;                        // internet: 10 Hz while moving, 1 Hz idle
    if (mqtt.connected() && (moving || now - lastPub >= 1000)) { lastPub = now; mqtt.publish(topic("state").c_str(), buf); }
#endif
  }
  if (now - lastOled >= 200) { lastOled = now; drawOled(); }
}
