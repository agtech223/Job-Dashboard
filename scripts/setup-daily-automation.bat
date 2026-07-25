@echo off
setlocal
title Academic Job Radar - daily automation

echo.
echo  ==========================================================
echo    ACADEMIC JOB RADAR - DAILY AUTOMATION
echo  ==========================================================
echo.
echo   This creates a Windows Scheduled Task that searches every
echo   job board once a day at 07:30 and updates your dashboard,
echo   so new positions are already waiting when you open it.
echo.
echo   No window will appear when it runs.
echo.
echo   NOTE: you only need this if you want the search to run on THIS
echo   computer. The GitHub Action already refreshes the live site
echo   every morning whether this machine is on or not.
echo.
set /p ANSWER=  Set this up now? (Y/N):
if /i not "%ANSWER%"=="Y" goto :cancelled

for /f "delims=" %%P in ('where pythonw 2^>nul') do set "PYW=%%P"
if not defined PYW (
  for /f "delims=" %%P in ('where python 2^>nul') do set "PYW=%%P"
)
if not defined PYW (
  echo.
  echo   Python was not found. Install it, then run this again.
  pause
  exit /b 1
)

schtasks /Create /TN "Academic Job Radar - Daily Refresh" ^
  /TR "\"%PYW%\" \"%~dp0..\engine\scraper.py\"" ^
  /SC DAILY /ST 07:30 /F >nul 2>&1

if errorlevel 1 (
  echo.
  echo   Could not create the task. Try running this file as
  echo   Administrator ^(right-click - Run as administrator^).
  pause
  exit /b 1
)

echo.
echo   Done. The search now runs every day at 07:30.
echo.
echo   To change the time :  search Windows for "Task Scheduler"
echo                         and look for "Academic Job Radar"
echo   To remove it       :  run REMOVE-DAILY-AUTOMATION.bat
echo.
pause
exit /b 0

:cancelled
echo.
echo   Cancelled - nothing was changed.
pause
