@echo off
cd /d "%~dp0"
title Jarvis HUD Debug Console
echo ========================================================
echo Launching Jarvis with Console Output for Debugging...
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
pause
