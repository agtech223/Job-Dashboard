@echo off
title Academic Job Radar - remove automation
schtasks /Delete /TN "Academic Job Radar - Daily Refresh" /F
echo.
echo   The daily automatic search has been removed.
echo   The dashboard still works - just press "Refresh from the web".
echo.
pause
