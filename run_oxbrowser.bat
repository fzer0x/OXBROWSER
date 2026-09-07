@echo off
cd /d "%~dp0"

REM Starte OXBROWSER ueber die digital signierte Python-Runtime (wird von Smart App Control nicht blockiert)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "main.py"
) else if exist "venv_build\Scripts\pythonw.exe" (
    start "" "venv_build\Scripts\pythonw.exe" "main.py"
) else (
    start "" pythonw "main.py"
)
