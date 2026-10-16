@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Run.ps1" -Action Render4K
if errorlevel 1 exit /b %errorlevel%
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Scripts\Run.ps1" -Action Encode4K
exit /b %errorlevel%
