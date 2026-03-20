@echo off
:: ============================================================
:: ClipSync Bridge — Silent Startup Launcher
:: Place a shortcut to this in your Windows Startup folder
:: or call it from AI-HUB.ahk at boot.
:: ============================================================

:: Check if already running
tasklist /FI "WINDOWTITLE eq ClipSync Bridge Server" 2>NUL | find /I "cmd.exe" >NUL
if not errorlevel 1 (
    exit /b 0
)

:: Launch minimized
start /MIN "ClipSync Bridge Server" cmd /c "cd /d "%~dp0" && python sync_server.py"
