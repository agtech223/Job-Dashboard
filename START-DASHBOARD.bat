@echo off
title Academic Job Radar
cd /d "%~dp0engine"

REM ---------------------------------------------------------------
REM  This is the only file you need at the top level.
REM  The other tools live in the scripts folder:
REM     scripts\refresh-now.bat              search without opening the UI
REM     scripts\setup-daily-automation.bat   schedule a daily local search
REM     scripts\remove-daily-automation.bat  undo that
REM     scripts\push-to-github.bat           publish changes to the live site
REM ---------------------------------------------------------------

where python >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python was not found on this computer.
  echo   Install it from https://www.python.org/downloads/  ^(tick "Add to PATH"^)
  echo.
  pause
  exit /b 1
)

python -c "import requests, feedparser" >nul 2>&1
if errorlevel 1 (
  echo   First run - installing the two libraries the engine needs...
  python -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt"
)

python server.py
pause
