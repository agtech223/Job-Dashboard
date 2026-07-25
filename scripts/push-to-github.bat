@echo off
setlocal
title Push to GitHub
cd /d "%~dp0.."

REM Reads the token from gh.txt.txt in the project root. That file is
REM git-ignored and never leaves this machine.
if not exist "gh.txt.txt" (
  echo.
  echo   gh.txt.txt not found in the project folder.
  echo   Put your GitHub token in that file first.
  pause & exit /b 1
)
set /p TOKEN=<gh.txt.txt

echo.
echo   Committing any local changes...
git add -A
git diff --staged --quiet && (echo   Nothing new to commit.) || git commit -m "Update job radar"

echo.
echo   Pulling anything new from GitHub...
git -c credential.helper= pull --rebase "https://%TOKEN%@github.com/agtech223/Job-Dashboard.git" main

echo.
echo   Pushing...
git -c credential.helper= push "https://%TOKEN%@github.com/agtech223/Job-Dashboard.git" main:main
if errorlevel 1 (
  echo.
  echo   Push failed. If it mentions the "workflow" scope, your token needs
  echo   the Workflows permission - see the README, section "Hosting".
) else (
  echo.
  echo   Pushed. The live site updates within a minute:
  echo   https://agtech223.github.io/Job-Dashboard/
)
echo.
pause
