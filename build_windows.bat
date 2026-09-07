@echo off
setlocal enabledelayedexpansion

REM Ensure we run from the project root directory
cd /d "%~dp0"

echo ============================================================
echo           OXBROWSER Windows Executable Builder (.exe)
echo ============================================================
echo.

REM 1. Detect existing virtual environment
if exist ".venv\Scripts\activate.bat" (
    echo [*] Using existing virtual environment: .venv
    call .venv\Scripts\activate.bat
    goto :venv_ready
)

if exist "venv_build\Scripts\activate.bat" (
    echo [*] Using existing virtual environment: venv_build
    call venv_build\Scripts\activate.bat
    goto :venv_ready
)

if exist "venv\Scripts\activate.bat" (
    echo [*] Using existing virtual environment: venv
    call venv\Scripts\activate.bat
    goto :venv_ready
)

REM No virtual environment found, detect Python
echo [*] No existing virtual environment found. Detecting Python...

python --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=python"
    goto :create_venv
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto :create_venv
)

echo [ERROR] Python is not found in PATH!
echo Please install Python 3.12+ 64-bit from https://www.python.org/
pause
exit /b 1

:create_venv
echo [*] Creating virtual environment '.venv'...
%PY_CMD% -m venv .venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)
call .venv\Scripts\activate.bat

:venv_ready
echo [*] Python detected:
python --version
echo.

REM 2. Check if PyInstaller is installed
python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing requirements and PyInstaller...
    python -m pip install --upgrade pip
    if exist "requirements.txt" (
        python -m pip install -r requirements.txt
    )
    python -m pip install pyinstaller
) else (
    echo [*] PyInstaller and dependencies already installed.
)

REM 3. Build Executable with PyInstaller
echo.
echo [*] Starting PyInstaller compilation with oxbrowser.spec...
python -m PyInstaller --clean -y oxbrowser.spec

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

REM 4. Create Smart App Control-friendly Shortcuts
echo [*] Erstelle Verknuepfungen (kompatibel mit Smart App Control)...
powershell -ExecutionPolicy Bypass -File "%~dp0create_shortcuts.ps1"

echo.
echo ============================================================
echo Startmoeglichkeiten fuer OXBROWSER:
echo   1. Desktop-Verknuepfung:  OXBROWSER (auf Ihrem Desktop)
echo   2. Projekt-Verknuepfung:  OXBROWSER.lnk (mit Icon, ohne Konsole)
echo   3. VBScript-Starter:      OXBROWSER.vbs (vollstaendig lautlos)
echo   4. Batch-Starter:         run_oxbrowser.bat
echo   5. PyInstaller EXE:       dist\OXBROWSER\OXBROWSER.exe
echo                              (nur ohne Smart App Control oder mit Zertifikat)
echo ============================================================
echo.
pause


