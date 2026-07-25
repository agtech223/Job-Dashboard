@echo off
title Academic Job Radar - refreshing
cd /d "%~dp0engine"
python scraper.py
echo.
echo   Done. Open the dashboard to see the results.
pause
