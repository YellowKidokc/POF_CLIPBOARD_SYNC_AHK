@echo off
:: ClipSync Bridge - Silent Startup Launcher
:: Uses full Python path to avoid PATH issues at system startup
setlocal

:: Check if already running by port
netstat -ano | findstr ":3456 " | findstr "LISTENING" >NUL 2>&1
if not errorlevel 1 (
    exit /b 0
)

set "PY_DIR=C:\Users\lowes\AppData\Local\Programs\Python\Python312"
set "PYW=%PY_DIR%\pythonw.exe"
set "PYC=%PY_DIR%\python.exe"
set "SCRIPT=C:\Users\lowes\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\AI-HUB-v2\clipsync-bridge\sync_server.py"

:: Prefer pythonw so the bridge server does not spawn a visible console window.
if exist "%PYW%" (
    start "" /B "%PYW%" "%SCRIPT%"
    exit /b 0
)

if exist "%PYC%" (
    start "" /MIN "%PYC%" "%SCRIPT%"
    exit /b 0
)

exit /b 1
