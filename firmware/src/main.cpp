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
// WiFi / AP / MQTT credentials live in secrets.h (git-ignored). Copy secrets.example.h to start.
#include "secrets.h"
const char* AP_SSID = "RobotArm";        // fallback access point -> 192.168.4.1
const uint32_t DEADMAN_MS = 2000;        // controllers send {"hb":1} every 500 ms; silence this long = hold position
// Option B: commands from Raspberry Pi over UART (Pi TXD -> GPIO16, Pi RXD <- GPIO17, GND)
#define USE_SERIAL2 1
const int SERIAL2_RX = 16, SERIAL2_TX = 17;

// ---- MQTT: control over the internet ----------------------------------------
#define USE_MQTT 1
#define MQTT_TLS 0                         // 1 = TLS (HiveMQ Cloud port 8883)
// MQTT_HOST / MQTT_PORT / MQTT_PREFIX come from secrets.h — use the private broker on the Pi for a real arm

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
uint32_t lastHb = 0;                     // dead-man: armed by the first heartbeat, trips once when they stop
bool deadmanArmed = false, deadmanTripped = false;
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
// {"j":[6]} {"ik":[x,y,z,pitch(,0=exact pitch)]} {"grip":v} {"speed":v} {"home":1} {"stop":1} {"status":1} {"hb":1}
String handleCommand(const char* txt) {
  JsonDocument d;
  if (deserializeJson(d, txt)) return "{\"err\":\"bad json\"}";
  if (d["hb"].is<int>()) { lastHb = millis(); deadmanArmed = true; deadmanTripped = false; return ""; }
  if (d["status"].is<int>()) {                      // polled by pi/arm_core.py to know when a move is done
    bool moving = false;
    for (int i = 0; i < 6; i++) if (fabsf(tgt[i] - cur[i]) > 0.5f) moving = true;
    char buf[128];
    snprintf(buf, sizeof buf, "{\"status\":[%.0f,%.0f,%.0f,%.0f,%.0f,%.0f],\"moving\":%s,\"deadman\":%s}",
             cur[0], cur[1], cur[2], cur[3], cur[4], cur[5], moving ? "true" : "false", deadmanTripped ? "true" : "false");
    return String(buf);
  }
  if (d["stop"].is<int>()) { setTargets(cur); return "{\"ok\":\"stop\"}"; }
  if (d["speed"].is<float>()) { speedDps = constrain(d["speed"].as<float>(), 10, 360); return "{\"ok\":\"speed\"}"; }
  if (deadmanTripped) return "{\"err\":\"deadman\"}";   // motion locked until a new {"hb":1}

  float a[6];
  memcpy(a, tgt, sizeof a);
  if (d["j"].is<JsonArray>()) {
    JsonArray j = d["j"];
    for (int i = 0; i < 6 && i < (int)j.size(); i++) if (j[i].is<float>()) a[i] = j[i];
  } else if (d["ik"].is<JsonArray>()) {
    JsonArray k = d["ik"];
    if (k.size() < 3 || !k[0].is<float>() || !k[1].is<float>() || !k[2].is<float>()) return "{\"err\":\"ik needs x,y,z\"}";
    float o[4];
    float pitch = k.size() > 3 ? k[3].as<float>() : -90;
    bool search = !(k.size() > 4 && k[4].as<int>() == 0);   // 5th value 0 = use exactly this pitch (like the sim)
    if (!(search ? autoIK(k[0], k[1], k[2], pitch, o) : solveIK(k[0], k[1], k[2], pitch, o))) return "{\"err\":\"unreachable\"}";
    for (int i = 0; i < 4; i++) a[i] = roundf(o[i] * 10) / 10;   // 0.1 deg, same as the sim
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

/* Polls incoming characters from a Stream, assembles them into lines and
   dispatches complete lines to a handler, replying on the same Stream. */
void pollLines(Stream& port, String& buf, String (*handler)(const char*)) {
    while (port.available()) {
        int ic = port.read();               // read next byte, -1 if none
        if (ic < 0) break;                  // safety guard
        char c = static_cast<char>(ic);
        if (buf == "\x01") {               // discarding the rest of an over-long line
            if (c == '\n' || c == '\r') buf = "";
            continue;
        }
        if (c == '\n' || c == '\r') {       // line terminator
            if (buf.length() > 0) {
                String reply = handler(buf.c_str());
                if (reply.length())
                    port.println(reply);
                else
                    port.println("{\"ok\":1}");
                buf = "";
            }
            // if buf empty, ignore extra terminators (e.g., CR+LF)
        } else {
            buf += c;                        // accumulate character
            if (buf.length() > 256) {        // overflow protection: drop until the next newline
                buf = "\x01";
                port.println("{\"err\":\"line too long\"}");
            }
        }
    }
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
// refuse the example/public prefix: it is published on GitHub, anyone could drive the arm
bool mqttAllowed() { return *MQTT_PREFIX && strncmp(MQTT_PREFIX, "robot101/", 9) != 0; }

void onMqtt(char* t, byte* payload, unsigned int len) {
  String msg;
  msg.reserve(len);
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  String reply = handleCommand(msg.c_str());
  if (reply.length()) mqtt.publish(topic("reply").c_str(), reply.c_str());
}

void mqttLoop() {
  if (!mqttAllowed() || WiFi.status() != WL_CONNECTED) return;   // AP fallback = no internet
  if (mqtt.connected()) { mqtt.loop(); return; }
  static uint32_t lastTry = 0, backoff = 3000;                   // 3 s -> 30 s while the broker is down
  if (lastTry && millis() - lastTry < backoff) return;
  lastTry = millis();
  String id = "arm-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  String st = topic("status");
  if (mqtt.connect(id.c_str(), *MQTT_USER ? MQTT_USER : nullptr, *MQTT_PASS ? MQTT_PASS : nullptr,
                   st.c_str(), 1, true, "offline")) {          // last will: offline (retained)
    mqtt.publish(st.c_str(), "online", true);
    mqtt.subscribe(topic("cmd").c_str());
    Serial.printf("MQTT connected: %s/cmd\n", MQTT_PREFIX);
    backoff = 3000;
  } else {
    backoff = min<uint32_t>(backoff * 2, 30000);
    Serial.printf("MQTT failed rc=%d, retry in %lus\n", mqtt.state(), (unsigned long)(backoff / 1000));
  }
}
#endif

// ---- display ------------------------------------------------------------------
void drawOled() {
  if (!oledOk) return;
  oled.clearDisplay();
  oled.setCursor(0, 0);
  oled.println(WiFi.status() == WL_CONNECTED ? WiFi.localIP() : WiFi.softAPIP());
  oled.printf("J1 %3.0f J2 %3.0f J3 %3.0f\n", cur[0], cur[1], cur[2]);
  oled.printf("J4 %3.0f J5 %3.0f G  %3.0f\n", cur[3], cur[4], cur[5]);
  oled.printf("spd %.0f  ws %u\n", speedDps, ws.connectedClients());
  if (deadmanTripped) { oled.setTextSize(2); oled.println("NO LINK"); oled.setTextSize(1); }
  oled.display();
}

// ---- setup / loop -------------------------------------------------------------
void setup() {
  Serial.begin(115200);
#if USE_SERIAL2
  Serial2.begin(115200, SERIAL_8N1, SERIAL2_RX, SERIAL2_TX);
#endif
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
  else {   // keep a hotspot up and keep retrying the home WiFi in loop()
    WiFi.mode(WIFI_AP_STA);
    WiFi.softAP(AP_SSID, AP_PASS);
    Serial.printf("\nAP %s  IP: %s\n", AP_SSID, WiFi.softAPIP().toString().c_str());
  }

  ws.begin();
  ws.onEvent(onWs);
#if USE_MQTT
#if MQTT_TLS
  mqttNet.setInsecure();   // demo only: skips certificate check, load the broker CA for real use
#endif
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqtt);
  mqtt.setBufferSize(512);
  mqtt.setSocketTimeout(2);   // an unreachable broker must not freeze servos for 15 s
  if (!mqttAllowed()) Serial.println("MQTT OFF: set a unique MQTT_PREFIX in secrets.h (not empty, not robot101/...)");
  if (strstr(MQTT_HOST, "hivemq.com")) Serial.println("WARNING: public MQTT broker - use the private broker on the Pi for a real arm");
#endif
  Serial.println("Ready. Send JSON per line, e.g. {\"ik\":[180,0,60,-90]}");
}

void loop() {
  ws.loop();
  bool stalled = false;
#if USE_MQTT
  uint32_t t0 = millis();
  mqttLoop();
  if (millis() - t0 > 300) { stalled = true; ws.loop(); }   // a slow connect: take heartbeats that queued meanwhile
#endif

  // AP fallback: retry the home WiFi every 60 s, drop the hotspot once connected
  static uint32_t lastWifiTry = 0;
  if (WiFi.getMode() == WIFI_AP_STA) {
    if (WiFi.status() == WL_CONNECTED) {
      WiFi.softAPdisconnect(true);
      WiFi.mode(WIFI_STA);
      Serial.printf("WiFi reconnected, IP: %s\n", WiFi.localIP().toString().c_str());
    } else if (millis() - lastWifiTry > 60000) {
      lastWifiTry = millis();
      WiFi.begin(WIFI_SSID, WIFI_PASS);
    }
  }

  // serial: one JSON command per line (USB, and Pi UART on Serial2)
  static String line0;
  pollLines(Serial, line0, handleCommand);
#if USE_SERIAL2
  static String line2;
  pollLines(Serial2, line2, handleCommand);
#endif

  // motion @ 50 Hz
  static uint32_t lastMove = millis();
  uint32_t now = millis();
  if (deadmanArmed && !stalled && now - lastHb > DEADMAN_MS) {   // skip one check right after our own stall   // controller went silent: stop and hold position
    deadmanArmed = false;
    deadmanTripped = true;
    setTargets(cur);
    Serial.println("DEAD-MAN: no heartbeat, holding position");
  }
  if (now - lastMove >= 20) {
    float dt = (now - lastMove) / 1000.0f;
    lastMove = now;
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
    snprintf(buf, sizeof buf, "{\"state\":[%.0f,%.0f,%.0f,%.0f,%.0f,%.0f],\"moving\":%s,\"deadman\":%s}",
             cur[0], cur[1], cur[2], cur[3], cur[4], cur[5], moving ? "true" : "false", deadmanTripped ? "true" : "false");
    ws.broadcastTXT(buf);
#if USE_MQTT
    static uint32_t lastPub = 0;                        // internet: 10 Hz while moving, 1 Hz idle
    if (mqtt.connected() && (moving || now - lastPub >= 1000)) { lastPub = now; mqtt.publish(topic("state").c_str(), buf); }
#endif
  }
  if (now - lastOled >= 200) { lastOled = now; drawOled(); }
}
