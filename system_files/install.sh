#!/usr/bin/env bash
# Firenze install script — run as root or with sudo
# Sets up the systemd service and verifies required Asterisk modules.

set -euo pipefail

APP_DIR="/home/zvn/public_apps/new-firenze"
SERVICE_NAME="new-firenze"
SERVICE_FILE="new-firenze.service"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Systemd service ──────────────────────────────────────────────────────────

if [ ! -f "${SYSTEMD_DIR}/${SERVICE_FILE}" ]; then
    echo "[+] Installing systemd service..."
    cp "${SCRIPT_DIR}/${SERVICE_FILE}" "${SYSTEMD_DIR}/${SERVICE_FILE}"
    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}"
    echo "[+] Service installed and enabled."
else
    echo "[=] Service file already present at ${SYSTEMD_DIR}/${SERVICE_FILE}, skipping."
fi

# ── Logs directory ───────────────────────────────────────────────────────────

if [ ! -d "${APP_DIR}/logs" ]; then
    echo "[+] Creating logs directory..."
    mkdir -p "${APP_DIR}/logs"
    chown zvn:zvn "${APP_DIR}/logs"
fi

# ── Python venv ───────────────────────────────────────────────────────────────

PYTHON_BIN="$(command -v python3.14 2>/dev/null || true)"
if [ -z "${PYTHON_BIN}" ]; then
    echo "[!] python3.14 not found in PATH — install it before continuing."
    exit 1
fi

if [ ! -d "${APP_DIR}/.venv" ]; then
    echo "[+] Creating virtualenv with $("${PYTHON_BIN}" --version)..."
    sudo -u zvn "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
    sudo -u zvn "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}[deploy]"
    echo "[+] Virtualenv ready."
else
    echo "[=] Virtualenv already exists, skipping."
fi

# ── Asterisk modules ──────────────────────────────────────────────────────────
#
# Required for the new CURL()-based AGI architecture:
#   func_curl.so   — provides CURL() dialplan function
#   func_json.so   — provides JSON_DECODE() dialplan function
#   res_pjsip.so   — PJSIP SIP stack
#   chan_pjsip.so  — PJSIP channel driver
#   res_agi.so     — AGI (still used for legacy audiotex calls)

echo ""
echo "[*] Checking Asterisk modules..."

REQUIRED_MODULES=(
    "func_curl"
    "func_json"
    "res_pjsip"
    "chan_pjsip"
    "res_agi"
)

ASTERISK_BIN="$(command -v asterisk 2>/dev/null || true)"
if [ -z "${ASTERISK_BIN}" ]; then
    echo "[!] asterisk binary not found — skipping module check."
else
    ALL_OK=true
    for mod in "${REQUIRED_MODULES[@]}"; do
        result=$(asterisk -rx "module show like ${mod}" 2>/dev/null | grep -c "${mod}" || true)
        if [ "${result}" -gt 0 ]; then
            echo "    [ok] ${mod}.so"
        else
            echo "    [MISSING] ${mod}.so — add to /etc/asterisk/modules.conf and run: asterisk -rx 'module load ${mod}.so'"
            ALL_OK=false
        fi
    done

    if [ "${ALL_OK}" = true ]; then
        echo "[+] All required Asterisk modules are loaded."
    else
        echo "[!] Some modules are missing. Fix before using CURL()-based AGI endpoints."
    fi
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "Done. Next steps:"
echo "  1. Make sure ${APP_DIR}/.env exists with SQLALCHEMY_DATABASE_URL set"
echo "  2. Run migrations: cd ${APP_DIR} && .venv/bin/alembic upgrade head"
echo "  3. Start service:  systemctl start ${SERVICE_NAME}"
echo "  4. Check status:   systemctl status ${SERVICE_NAME}"
