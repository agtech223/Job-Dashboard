@echo off
title Academic Job Radar
cd /d "%~dp0engine"

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
  python -m pip install --quiet --disable-pip-version-check requests feedparser
)

python server.py
pause
