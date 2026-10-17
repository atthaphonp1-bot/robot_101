#!/usr/bin/env bash
# pi/setup-planner.sh
# Installs the robot_101 VLM planner server as a systemd service on Raspberry Pi 5.
# Safe to re-run. Thai user-facing messages.

set -euo pipefail

# ----- Helper functions -----
say() {
    printf "\e[1;34m==> %s\e[0m\n" "$*" >&2
}

fail() {
    printf "\e[1;31mError: %s\e[0m\n" "$*" >&2
    exit 1
}

# ----- Preconditions -----
if [[ "$(uname -s)" != "Linux" ]]; then
    fail "This script must be run on Linux."
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVER_PATH="${REPO_DIR}/vlm/planner_server.py"

if [[ ! -f "${SERVER_PATH}" ]]; then
    fail "Planner server not found at ${SERVER_PATH}"
fi

if ! command -v sudo >/dev/null 2>&1; then
    fail "sudo is required but not found."
fi

# ----- Variables -----
RUN_USER="${SUDO_USER:-$USER}"
PORT=8792
HOST_NAME="$(hostname)"
IP="$(hostname -I | awk '{print $1}')"

# ----- Install dependencies -----
say "Installing required packages (python3-opencv, python3-numpy, curl)..."
sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q python3-opencv python3-numpy curl

# ----- Prepare configuration directory -----
CONFIG_DIR="/etc/robot101"
say "Ensuring configuration directory ${CONFIG_DIR} exists with proper permissions..."
sudo install -d -m 755 "${CONFIG_DIR}"

# ----- Environment file -----
ENV_FILE="${CONFIG_DIR}/planner.env"
if [[ ! -f "${ENV_FILE}" ]]; then
    say "No existing planner.env found. Setting up a new one."
    # Read API key silently from the controlling terminal
    IFS= read -rsp $'\nAnthropic API key (กด Enter เพื่อข้าม ใช้ mock planner): ' API_KEY </dev/tty
    printf "\n" >&2  # newline after the prompt

    # Build temporary file with correct permissions
    TMPFILE=$(mktemp)
    {
        echo "PLANNER_HOST=0.0.0.0"
        echo "PLANNER_PORT=${PORT}"
        echo "PLANNER_ORIGINS=http://${HOST_NAME}.local:8080,http://${IP}:8080,http://localhost:8791"
        if [[ -n "${API_KEY}" ]]; then
            echo "ANTHROPIC_API_KEY=${API_KEY}"
        fi
    } > "${TMPFILE}"
    chmod 600 "${TMPFILE}"
    sudo mv "${TMPFILE}" "${ENV_FILE}"
    sudo chown root:root "${ENV_FILE}"
    say "Created ${ENV_FILE} (mode 600, owned by root)."
else
    say "Existing ${ENV_FILE} found – keeping it unchanged."
    say "To edit it later run: sudo nano ${ENV_FILE}"
fi

# ----- Systemd service file -----
SERVICE_FILE="/etc/systemd/system/robot-planner.service"
say "Installing systemd service to ${SERVICE_FILE}..."
sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=robot_101 VLM planner
After=network-online.target
Wants=network-online.target

[Service]
User=${RUN_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${SERVER_PATH}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

# ----- Enable and start service -----
say "Reloading systemd daemon..."
sudo systemctl daemon-reload

say "Enabling and starting robot-planner service..."
sudo systemctl enable --now robot-planner
sudo systemctl restart robot-planner

# ----- Health check -----
say "Waiting for planner to become healthy (up to 10 seconds)..."
HEALTH_OK=0
for i in {1..10}; do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
        HEALTH_OK=1
        break
    fi
    sleep 1
done

if [[ ${HEALTH_OK} -eq 1 ]]; then
    HEALTH_JSON=$(curl -sS "http://127.0.0.1:${PORT}/health")
    say "✓ Planner is healthy: ${HEALTH_JSON}"
else
    say "✗ Planner health check failed."
    say "Hint: sudo journalctl -u robot-planner -n 30"
    exit 1
fi

# ----- Summary -----
printf "\n"
printf "+------------------- Summary -------------------+\n"
printf "| Simulator URL: http://%s.local:8080/ (แท็บ กล้อง → สั่งด้วยข้อความ) |\n" "${HOST_NAME}"
printf "| Planner URL:   http://%s.local:%d/health |\n" "${HOST_NAME}" "${PORT}"
printf "| เพิ่ม/เปลี่ยน API key: sudo nano %s แล้ว sudo systemctl restart robot-planner |\n" "${ENV_FILE}"
printf "| ดู log: journalctl -u robot-planner -f |\n"
printf "+---------------------------------------------+\n"

exit 0