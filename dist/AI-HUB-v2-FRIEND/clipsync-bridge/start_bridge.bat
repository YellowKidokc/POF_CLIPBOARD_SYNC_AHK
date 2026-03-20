@echo off
title ClipSync Bridge Server
echo ============================================================
echo   ClipSync Bridge — Starting...
echo ============================================================
echo.

:: Set remote sync (update these with your real values)
:: set CLIPSYNC_REMOTE=https://clipsync-api.davidokc28.workers.dev
:: set CLIPSYNC_TOKEN=your-bearer-token

cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH
    echo Install Python 3.10+ and add to PATH
    pause
    exit /b 1
)

:: Start the server
echo Starting sync server on http://localhost:3456 ...
python sync_server.py

:: If Python exits, keep window open to see errors
echo.
echo Server stopped. Press any key to exit...
pause >nul
