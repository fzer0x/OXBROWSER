#!/usr/bin/env bash
# OXBROWSER Linux Launcher Script (Optimized for Arch, CachyOS, Debian/Ubuntu & Fedora)
set -e

# Resolve canonical script directory (handling symlinks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "          OXBROWSER Linux Launcher"
echo "============================================================"
echo ""

# Find existing virtualenv
VENV_DIR=""
if [ -d "$SCRIPT_DIR/.venv" ]; then
    VENV_DIR="$SCRIPT_DIR/.venv"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    VENV_DIR="$SCRIPT_DIR/venv"
fi

# Function to fix relocated virtualenv paths
repair_venv_paths() {
    local target_venv="$1"
    if [ -f "$target_venv/bin/activate" ]; then
        local old_venv
        old_venv=$(grep "^VIRTUAL_ENV=" "$target_venv/bin/activate" 2>/dev/null | head -n 1 | cut -d"'" -f2)
        if [ -n "$old_venv" ] && [ "$old_venv" != "$target_venv" ]; then
            echo "[*] Detected relocated virtual environment (was: $old_venv -> now: $target_venv)"
            echo "[*] Auto-repairing venv configuration & shebangs..."
            sed -i "s|$old_venv|$target_venv|g" "$target_venv/bin/activate"* 2>/dev/null || true
            sed -i "s|$old_venv|$target_venv|g" "$target_venv/bin/"* 2>/dev/null || true
        fi
    fi
}

# 1. Detect or create virtual environment
if [ -n "$VENV_DIR" ] && [ -x "$VENV_DIR/bin/python" ]; then
    echo "[*] Using existing virtual environment: $VENV_DIR"
    repair_venv_paths "$VENV_DIR"
    VENV_PYTHON="$VENV_DIR/bin/python"
    # Source activate for environment variables
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
else
    echo "[*] No working virtual environment found. Initializing .venv..."
    
    # Check for best Python candidate (prefer 3.12 / 3.11 / uv, as 3.14+ lacks wheels for some packages)
    PYTHON_CMD=""
    if command -v uv &>/dev/null; then
        echo "[*] Found uv. Creating Python 3.12 virtual environment..."
        uv venv --python 3.12 .venv || uv venv .venv
        VENV_DIR="$SCRIPT_DIR/.venv"
        VENV_PYTHON="$VENV_DIR/bin/python"
        source "$VENV_DIR/bin/activate"
        echo "[*] Installing requirements using uv..."
        uv pip install -r requirements.txt
    else
        for py in python3.12 python3.11 python3.10 python3; do
            if command -v "$py" &>/dev/null; then
                PY_VER=$("$py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
                PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
                PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
                if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ] && [ "$PY_MINOR" -le 13 ]; then
                    PYTHON_CMD="$py"
                    break
                elif [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 14 ]; then
                    echo "[!] Notice: $py is version $PY_VER. Python 3.14+ may lack pre-built wheels for PyQt6/camoufox/ddddocr."
                    PYTHON_CMD="$py"
                fi
            fi
        done

        if [ -z "$PYTHON_CMD" ]; then
            echo "[ERROR] Suitable Python interpreter not found!"
            echo "Please install Python 3.12 or 'uv':"
            echo "  - Arch / CachyOS:  sudo pacman -S python python-pip || curl -LsSf https://astral.sh/uv/install.sh | sh"
            echo "  - Debian / Ubuntu: sudo apt install python3 python3-venv python3-pip"
            echo "  - Fedora:          sudo dnf install python3 python3-pip"
            exit 1
        fi

        echo "[*] Creating virtual environment using $PYTHON_CMD..."
        "$PYTHON_CMD" -m venv .venv
        VENV_DIR="$SCRIPT_DIR/.venv"
        VENV_PYTHON="$VENV_DIR/bin/python"
        source "$VENV_DIR/bin/activate"
        echo "[*] Upgrading pip and installing requirements..."
        "$VENV_PYTHON" -m pip install --upgrade pip
        "$VENV_PYTHON" -m pip install -r requirements.txt
    fi

    echo "[*] Installing Playwright browsers..."
    "$VENV_PYTHON" -m playwright install chromium firefox || true
fi

# Ensure VENV_PYTHON is valid
if [ -z "$VENV_PYTHON" ] || [ ! -x "$VENV_PYTHON" ]; then
    VENV_PYTHON="$(which python3)"
fi

echo "[*] Python environment: $("$VENV_PYTHON" --version) at $VENV_PYTHON"
echo "[*] Launching OXBROWSER..."
echo ""

exec "$VENV_PYTHON" main.py "$@"
