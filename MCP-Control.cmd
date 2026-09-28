@echo off
cd /d "%~dp0"
where py >nul 2>nul || (
  echo Python 3.12 is required.
  pause
  exit /b 1
)
py -3.12 desktop_control.py
