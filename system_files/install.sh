#!/usr/bin/env bash
# Firenze install script — run as the zvn user, not root.
# Uses sudo internally only where needed.

set -euo pipefail

APP_DIR="/home/zvn/public_apps/new-firenze"
SERVICE_NAME="new-firenze"
SERVICE_FILE="new-firenze.service"
SYSTEMD_DIR="/etc/systemd/system"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE="${1:-}"

# ── Systemd service ──────────────────────────────────────────────────────────

DEST="${SYSTEMD_DIR}/${SERVICE_FILE}"
SRC="${SCRIPT_DIR}/${SERVICE_FILE}"

if [ ! -f "${DEST}" ] || [ "${SRC}" -nt "${DEST}" ] || [ "${FORCE}" = "--force" ]; then
    echo "[+] Installing/updating systemd service..."
    sudo cp "${SRC}" "${DEST}"
    sudo systemctl daemon-reload
    sudo systemctl enable "${SERVICE_NAME}"
    echo "[+] Done."
else
    echo "[=] Service file is up to date. Use --force to overwrite."
fi

# ── Logs directory ───────────────────────────────────────────────────────────

mkdir -p "${APP_DIR}/logs"

# ── Python venv ───────────────────────────────────────────────────────────────

PYTHON_BIN="$(command -v python3.14 2>/dev/null \
    || pyenv which python3.14 2>/dev/null \
    || { pyenv local 3.14.3 && pyenv which python3.14; } 2>/dev/null \
    || true)"

if [ -z "${PYTHON_BIN}" ]; then
    echo "[!] python3.14 not found. Install it with: pyenv install 3.14.3"
    exit 1
fi

if [ ! -d "${APP_DIR}/.venv" ]; then
    echo "[+] Creating virtualenv with $("${PYTHON_BIN}" --version)..."
    "${PYTHON_BIN}" -m venv "${APP_DIR}/.venv"
    "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}[deploy]"
    echo "[+] Virtualenv ready."
else
    echo "[=] Virtualenv already exists, skipping."
fi

# ── Asterisk modules ──────────────────────────────────────────────────────────

echo ""
echo "[*] Checking Asterisk modules..."

REQUIRED_MODULES=(func_curl func_json res_pjsip chan_pjsip res_agi)

if ! command -v asterisk &>/dev/null; then
    echo "[!] asterisk not found — skipping module check."
else
    ALL_OK=true
    for mod in "${REQUIRED_MODULES[@]}"; do
        if asterisk -rx "module show like ${mod}" 2>/dev/null | grep -q "${mod}"; then
            echo "    [ok] ${mod}.so"
        else
            echo "    [MISSING] ${mod}.so"
            ALL_OK=false
        fi
    done
    ${ALL_OK} || echo "[!] Load missing modules: asterisk -rx 'module load <name>.so'"
fi

# ── Done ─────────────────────────────────────────────────────────────────────

echo ""
echo "Next steps:"
echo "  1. Ensure ${APP_DIR}/.env has SQLALCHEMY_DATABASE_URL"
echo "  2. ${APP_DIR}/.venv/bin/alembic upgrade head"
echo "  3. sudo systemctl start ${SERVICE_NAME}"
