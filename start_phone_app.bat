@echo off
title JARVIS Phone App Server
cd /d "%~dp0"
echo ===================================================
echo Starting JARVIS Phone Server & Cloudflare Tunnel...
echo ===================================================
".\.venv\Scripts\python.exe" run_phone_app.py
pause
