@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ============================================================
echo      OXBROWSER Portable Package Builder (Smart App Control Safe)
echo ============================================================
echo.

set "DIST_PORTABLE=dist\OXBROWSER_PORTABLE"

echo [*] Zielverzeichnis: %DIST_PORTABLE%
if exist "%DIST_PORTABLE%" (
    echo [*] Raeume altes Verzeichnis auf...
    rmdir /s /q "%DIST_PORTABLE%"
)
mkdir "%DIST_PORTABLE%"

REM 1. Kopiere Python Runtime (.venv)
echo [*] Kopiere Python Runtime (.venv)...
if exist ".venv" (
    xcopy /e /i /y /q ".venv" "%DIST_PORTABLE%\.venv"
) else (
    echo [ERROR] .venv nicht gefunden! Bitte zuerst build_windows.bat ausfuehren.
    pause
    exit /b 1
)

REM 2. Kopiere Anwendungsdateien
echo [*] Kopiere Anwendungsdateien...
copy /y "main.py" "%DIST_PORTABLE%\"
copy /y "config.py" "%DIST_PORTABLE%\"
copy /y "oxbrowser.ico" "%DIST_PORTABLE%\"
copy /y "oxbrowser.png" "%DIST_PORTABLE%\"
copy /y "README.md" "%DIST_PORTABLE%\"
if exist "app_config.vault" copy /y "app_config.vault" "%DIST_PORTABLE%\"

echo [*] Kopiere Module...
xcopy /e /i /y /q "engine" "%DIST_PORTABLE%\engine"
xcopy /e /i /y /q "ui" "%DIST_PORTABLE%\ui"
xcopy /e /i /y /q "storage" "%DIST_PORTABLE%\storage"
if exist "models" xcopy /e /i /y /q "models" "%DIST_PORTABLE%\models"
if exist "extensions" xcopy /e /i /y /q "extensions" "%DIST_PORTABLE%\extensions"

REM 3. Erstelle Starter fuer das portable Paket
echo [*] Erstelle Starter-Skripte...

REM VBScript Launcher (Lautlos)
(
echo Set objShell = CreateObject^("WScript.Shell"^)
echo Set objFSO = CreateObject^("Scripting.FileSystemObject"^)
echo strPath = objFSO.GetParentFolderName^(WScript.ScriptFullName^)
echo strPythonw = strPath ^& "\.venv\Scripts\pythonw.exe"
echo strMain = strPath ^& "\main.py"
echo objShell.CurrentDirectory = strPath
echo objShell.Run Chr^(34^) ^& strPythonw ^& Chr^(34^) ^& " " ^& Chr^(34^) ^& strMain ^& Chr^(34^), 0, False
) > "%DIST_PORTABLE%\OXBROWSER.vbs"

REM Batch Launcher (mit Konsole fuer Debugging)
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" ".venv\Scripts\pythonw.exe" "main.py"
) > "%DIST_PORTABLE%\OXBROWSER.bat"

REM Desktop-Verknuepfungsersteller
(
echo @echo off
echo powershell -Command "$Wsh = New-Object -ComObject WScript.Shell; $S = $Wsh.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\OXBROWSER.lnk'); $S.TargetPath = '%%~dp0.venv\Scripts\pythonw.exe'; $S.Arguments = '\"%%~dp0main.py\"'; $S.WorkingDirectory = '%%~dp0'; $S.IconLocation = '%%~dp0oxbrowser.ico,0'; $S.Save()"
echo echo Verknuepfung auf dem Desktop wurde erstellt!
echo pause
) > "%DIST_PORTABLE%\Verknuepfung_auf_Desktop_erstellen.bat"

echo.
echo ============================================================
echo [SUCCESS] Portables Paket erfolgreich erstellt!
echo Verzeichnis: %DIST_PORTABLE%\
echo.
echo Dieses Paket laeuft auf jedem Windows 11 PC (auch mit Smart App Control),
echo da die Python-Runtime digital von der Python Foundation signiert ist.
echo ============================================================
echo.
pause
