@echo off
setlocal
cd /d "%~dp0"

where pythonw.exe >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.12 and run:
    echo     python -m pip install -r requirements.txt
    pause
    exit /b 1
)

start "" pythonw.exe "%~dp0main.py"

