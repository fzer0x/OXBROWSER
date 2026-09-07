$projectDir = (Get-Item -Path $PSScriptRoot).FullName
$pythonw = Join-Path $projectDir ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $alt = Join-Path $projectDir "venv_build\Scripts\pythonw.exe"
    if (Test-Path $alt) { $pythonw = $alt }
}

$mainPy = Join-Path $projectDir "main.py"
$iconPath = Join-Path $projectDir "oxbrowser.ico"

$WshShell = New-Object -ComObject WScript.Shell

# 1. Shortcut in the project folder: OXBROWSER.lnk
$rootLnk = Join-Path $projectDir "OXBROWSER.lnk"
$Shortcut = $WshShell.CreateShortcut($rootLnk)
$Shortcut.TargetPath = $pythonw
$Shortcut.Arguments = "`"$mainPy`""
$Shortcut.WorkingDirectory = $projectDir
if (Test-Path $iconPath) {
    $Shortcut.IconLocation = "$iconPath,0"
}
$Shortcut.Description = "OXBROWSER - Multi-Engine Anti-Detect Browser"
$Shortcut.Save()
Write-Host "Created root shortcut: $rootLnk"

# 2. Desktop shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
if (Test-Path $desktopPath) {
    $desktopLnk = Join-Path $desktopPath "OXBROWSER.lnk"
    $DesktopShortcut = $WshShell.CreateShortcut($desktopLnk)
    $DesktopShortcut.TargetPath = $pythonw
    $DesktopShortcut.Arguments = "`"$mainPy`""
    $DesktopShortcut.WorkingDirectory = $projectDir
    if (Test-Path $iconPath) {
        $DesktopShortcut.IconLocation = "$iconPath,0"
    }
    $DesktopShortcut.Description = "OXBROWSER - Multi-Engine Anti-Detect Browser"
    $DesktopShortcut.Save()
    Write-Host "Created Desktop shortcut: $desktopLnk"
}
