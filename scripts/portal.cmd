@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
  echo Uso: portal.cmd ^<start^|stop^|restart^|status^|logs^|validate^> [-Port PUERTO]
  exit /b 2
)

powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%portal.ps1" %*
exit /b %ERRORLEVEL%
