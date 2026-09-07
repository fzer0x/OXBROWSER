@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo           OXBROWSER Windows Executable Builder (.exe)
echo ============================================================
echo.

REM 1. Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.12+ (64-bit) from https://www.python.org/
    pause
    exit /b 1
)

echo [*] Python detected:
python --version

REM 2. Create and activate virtual environment if not present
if not exist "venv_build" (
    echo [*] Creating virtual environment 'venv_build'...
    python -m venv venv_build
)

call venv_build\Scripts\activate.bat

REM 3. Install required packages
echo [*] Installing requirements and PyInstaller...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller

REM 4. Build Executable with PyInstaller
echo.
echo [*] Starting PyInstaller compilation with oxbrowser.spec...
pyinstaller --clean -y oxbrowser.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the output above for error details.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo [SUCCESS] Build complete!
echo Executable directory: dist\OXBROWSER\
echo Main Executable:      dist\OXBROWSER\OXBROWSER.exe
echo ============================================================
echo.
pause
