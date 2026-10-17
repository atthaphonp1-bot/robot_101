#!/usr/bin/env bash
# Raspberry Pi 5 setup (target board; Pi 4 likely works, untested) for robot_101 — run once on the Pi (Raspberry Pi OS Lite 64-bit):
#   git clone https://github.com/atthaphonp1-bot/robot_101.git ~/robot_101
#   bash ~/robot_101/pi/setup.sh
# Security: Mosquitto is LAN-only, password-protected, NOT encrypted (no TLS/ACL) — keep it off the internet.
# Installs: Mosquitto (password, :1883 for ESP32, :9001 WebSocket for browsers),
#           OpenCV for vision_pick.py, and a web server for sim/ on :8080 (starts at boot).
# Safe to re-run: it rewrites its own config and keeps everything else.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_PORT=8080
RUN_USER="${SUDO_USER:-$USER}"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

[[ "$(uname -s)" == Linux ]] || fail "รันสคริปต์นี้บน Raspberry Pi (Linux) เท่านั้น"
[[ -f "$REPO_DIR/sim/index.html" ]] || fail "ไม่พบ $REPO_DIR/sim — clone repo ก่อน"
command -v sudo >/dev/null || fail "ต้องมี sudo"

# ---- MQTT account (asked once, never stored in plain text) -------------------
say "ตั้งบัญชี MQTT (ใช้ใน firmware secrets.h และหน้าเว็บ)"
read -rp "MQTT username [robot]: " MQ_USER </dev/tty
MQ_USER="${MQ_USER:-robot}"
while true; do
  read -rsp "MQTT password (อย่างน้อย 8 ตัว): " MQ_PASS </dev/tty; echo
  read -rsp "พิมพ์ซ้ำ: " MQ_PASS2 </dev/tty; echo
  [[ ${#MQ_PASS} -ge 8 && "$MQ_PASS" == "$MQ_PASS2" ]] && break
  echo "รหัสสั้นเกินหรือไม่ตรงกัน ลองใหม่"
done

# ---- packages -----------------------------------------------------------------
say "ติดตั้งแพ็กเกจ (ใช้เวลาสักครู่)"
sudo apt-get update -q
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q \
  mosquitto mosquitto-clients python3-opencv python3-numpy python3-websocket git

# ---- Mosquitto ----------------------------------------------------------------
say "ตั้งค่า Mosquitto"
sudo tee /etc/mosquitto/conf.d/robot.conf >/dev/null <<'EOF'
# robot_101 — managed by pi/setup.sh
allow_anonymous false
password_file /etc/mosquitto/passwd

listener 1883
protocol mqtt

listener 9001
protocol websockets
EOF
sudo touch /etc/mosquitto/passwd
sudo mosquitto_passwd -b /etc/mosquitto/passwd "$MQ_USER" "$MQ_PASS"
unset MQ_PASS MQ_PASS2
sudo chown mosquitto:mosquitto /etc/mosquitto/passwd
sudo chmod 600 /etc/mosquitto/passwd
sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto

# ---- web server for sim/ ------------------------------------------------------
say "ตั้งเว็บเซิร์ฟเวอร์ :$WEB_PORT (เปิดอัตโนมัติตอนบูต)"
sudo tee /etc/systemd/system/robot-web.service >/dev/null <<EOF
[Unit]
Description=robot_101 web (sim + remote dashboard + docs)
After=network-online.target
Wants=network-online.target

[Service]
User=$RUN_USER
WorkingDirectory=$REPO_DIR/sim
ExecStart=/usr/bin/python3 -m http.server $WEB_PORT --bind 0.0.0.0
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now robot-web
sudo systemctl restart robot-web

# ---- checks -------------------------------------------------------------------
say "ตรวจสอบ"
sleep 2
ok() { printf '  \033[32m✓\033[0m %s\n' "$*"; }
bad() { printf '  \033[31m✗\033[0m %s\n' "$*"; }
systemctl is-active --quiet mosquitto && ok "Mosquitto ทำงาน" || bad "Mosquitto ไม่ทำงาน: sudo journalctl -u mosquitto -n 30"
systemctl is-active --quiet robot-web && ok "เว็บทำงาน" || bad "เว็บไม่ทำงาน: sudo journalctl -u robot-web -n 30"
python3 -c "import cv2, numpy, websocket" 2>/dev/null && ok "OpenCV $(python3 -c 'import cv2;print(cv2.__version__)')" || bad "import OpenCV ไม่ได้"
mosquitto_pub -h localhost -u "$MQ_USER" -P x -t test -m x 2>/dev/null && bad "MQTT รับรหัสผิดได้ (ไม่ควรเกิด)" || ok "MQTT ปฏิเสธรหัสผิด"

IP="$(hostname -I | awk '{print $1}')"
HOST="$(hostname).local"
cat <<EOF

────────────────────────────────────────────────────────
 เสร็จแล้ว  Pi: $IP  ($HOST)

 เว็บ (มือถือ/คอม วง WiFi เดียวกัน)
   Simulator    http://$HOST:$WEB_PORT/
   แดชบอร์ด      http://$HOST:$WEB_PORT/remote.html
   เอกสาร       http://$HOST:$WEB_PORT/docs/

 ในหน้าเว็บ: Broker = ws://$HOST:9001   user = $MQ_USER

 firmware/src/secrets.h:
   MQTT_HOST = "$IP"        (ESP32 ไม่รู้จัก .local ใช้ IP แทน)
   MQTT_USER = "$MQ_USER"   MQTT_PASS = (รหัสที่เพิ่งตั้ง)
   MQTT_PREFIX = ชื่อเฉพาะของคุณ (ห้ามว่าง ห้ามขึ้นต้น robot101/)

 ทดสอบ: mosquitto_sub -h localhost -u $MQ_USER -P '<รหัส>' -t '#' -v
────────────────────────────────────────────────────────
EOF
