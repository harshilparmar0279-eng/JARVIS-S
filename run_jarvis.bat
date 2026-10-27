@echo off
cd /d "%~dp0"
title Jarvis HUD
echo Starting Jarvis HUD...
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    start "" pythonw main.py
)
exit
