@echo off
title Orkay AI Agent — Server
cd /d "%~dp0"
echo Starting Orkay AI Agent Dashboard...
echo.
echo Dashboard will open at: http://localhost:8000
echo Keep this window open while using the dashboard.
echo.
start "" "http://localhost:8000"
python server.py
pause
