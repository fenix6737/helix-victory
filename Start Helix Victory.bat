@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-helix.ps1"
if errorlevel 1 (
  echo.
  echo 起動に失敗しました。data\autostart.log を確認してください。
  pause
  exit /b 1
)
exit /b 0
