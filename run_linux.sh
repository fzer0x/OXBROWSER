#!/usr/bin/env bash
# OXBROWSER Linux Launcher Script
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "          OXBROWSER Linux Launcher"
echo "============================================================"
echo ""

# 1. Detect or create virtual environment
if [ -f ".venv/bin/activate" ]; then
    echo "[*] Using existing virtual environment: .venv"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo "[*] Using existing virtual environment: venv"
    source venv/bin/activate
else
    echo "[*] No virtual environment found. Initializing .venv..."
    if ! command -v python3 &>/dev/null; then
        echo "[ERROR] python3 not found! Please install Python 3.12+ (apt install python3 python3-venv python3-pip)"
        exit 1
    fi
    python3 -m venv .venv
    source .venv/bin/activate
    echo "[*] Upgrading pip and installing requirements..."
    pip install --upgrade pip
    pip install -r requirements.txt
    playwright install chromium firefox
fi

echo "[*] Python environment: $(python3 --version)"
echo "[*] Launching OXBROWSER..."
echo ""

exec python3 main.py "$@"
