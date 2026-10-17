// Copy to secrets.h and fill in your own values.
#pragma once
const char* WIFI_SSID = "Wokwi-GUEST";   // your router SSID for the real arm
const char* WIFI_PASS = "";
const char* AP_PASS = "change-me-123";            // fallback hotspot "RobotArm" (>= 8 chars)
const char* MQTT_USER = "";
const char* MQTT_PASS = "";
const char* MQTT_PREFIX = "your-unique-name/arm1";        // must match the prefix typed in the web sim / phone dashboard
const char* MQTT_HOST = "192.168.1.50";       // IP of the Raspberry Pi running Mosquitto (ESP32 cannot resolve .local)
const int MQTT_PORT = 1883;                    // private broker on the Pi with MQTT_USER / MQTT_PASS — never a public broker for a real arm
