@echo off
setlocal enabledelayedexpansion
title Push to GitHub
cd /d "%~dp0"

REM Reads the token from gh.txt.txt, which is git-ignored and never committed.
if not exist "gh.txt.txt" (
  echo.
  echo   gh.txt.txt not found - put your GitHub token in that file first.
  pause & exit /b 1
)
set /p TOKEN=<gh.txt.txt

echo.
echo   Committing any local changes...
git add -A
git diff --staged --quiet && (echo   Nothing new to commit.) || git commit -m "Update job radar"

echo.
echo   Pushing to github.com/agtech223/Job-Dashboard ...
git -c credential.helper= push "https://%TOKEN%@github.com/agtech223/Job-Dashboard.git" main:main

echo.
echo   Done. If the workflow file was rejected, your token needs the
echo   "Workflows" permission - see README, section "Email alerts".
echo.
pause
