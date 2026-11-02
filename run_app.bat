@echo off
title Wuthering Waves Echo Scanner
cd /d "%~dp0"

:: Check for administrative rights (needed to intercept hotkeys when game is focused)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator privileges so hotkeys work while Wuthering Waves is active...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'C:\Users\dAYAn\miniconda3\python.exe' -ArgumentList '\"%~dp0app.py\"' -WorkingDirectory '\"%~dp0\"' -Verb RunAs"
    exit /b
)

"C:\Users\dAYAn\miniconda3\python.exe" app.py
