@echo off
title Academic Job Radar - refreshing
cd /d "%~dp0..\engine"

python scraper.py
if errorlevel 1 goto :fail

REM Sends an alert only if the MAIL_* environment variables are set on this
REM machine. On GitHub the workflow supplies them from repository secrets.
python notify.py

echo.
echo   Done. Open the dashboard to see the results.
pause
exit /b 0

:fail
echo.
echo   The search failed. Check your internet connection and try again.
pause
exit /b 1
