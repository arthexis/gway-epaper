@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "RUNDIR=%ROOT%\.run"
set "PIDFILE=%RUNDIR%\epaper.pid"
set "LOGFILE=%RUNDIR%\epaper.log"
if not defined EPAPER_CONFIG set "EPAPER_CONFIG=%ROOT%\epaper.toml"
if not defined PYTHON set "PYTHON=python"
set "PYTHONPATH=%ROOT%\src;%PYTHONPATH%"

if "%~1"=="" goto :usage
if /I "%~1"=="start" goto :start
if /I "%~1"=="stop" goto :stop
if /I "%~1"=="restart" goto :restart
if /I "%~1"=="status" goto :status
if /I "%~1"=="run" goto :run
goto :usage

:ensure_rundir
if not exist "%RUNDIR%" mkdir "%RUNDIR%"
exit /b 0

:is_running
if not exist "%PIDFILE%" exit /b 1
set /p EPAPER_PID=<"%PIDFILE%"
if not defined EPAPER_PID exit /b 1
powershell -NoProfile -Command "if (Get-Process -Id %EPAPER_PID% -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >nul 2>nul
exit /b %ERRORLEVEL%

:start
call :ensure_rundir
call :is_running
if not errorlevel 1 (
    echo gway-epaper already running ^(pid !EPAPER_PID!^)
    exit /b 0
)
if exist "%PIDFILE%" del /q "%PIDFILE%"
powershell -NoProfile -Command "$env:PYTHONPATH='%ROOT%\src;' + $env:PYTHONPATH; $env:EPAPER_CONFIG_PATH='%EPAPER_CONFIG%'; $p=Start-Process -FilePath '%PYTHON%' -ArgumentList '-c','from gway_epaper.runtime import run_forever; import os; run_forever(os.environ[\"EPAPER_CONFIG_PATH\"])' -WorkingDirectory '%ROOT%' -RedirectStandardOutput '%LOGFILE%' -RedirectStandardError '%LOGFILE%.err' -WindowStyle Hidden -PassThru; Set-Content -Path '%PIDFILE%' -Value $p.Id"
if errorlevel 1 (
    echo gway-epaper failed to start 1>&2
    exit /b 1
)
timeout /t 1 /nobreak >nul
call :is_running
if errorlevel 1 (
    if exist "%PIDFILE%" del /q "%PIDFILE%"
    echo gway-epaper failed to start; see %LOGFILE% 1>&2
    exit /b 1
)
echo gway-epaper started ^(pid !EPAPER_PID!^)
exit /b 0

:stop
call :is_running
if errorlevel 1 (
    if exist "%PIDFILE%" del /q "%PIDFILE%"
    echo gway-epaper not running
    exit /b 0
)
powershell -NoProfile -Command "Stop-Process -Id %EPAPER_PID% -ErrorAction Stop"
if errorlevel 1 exit /b 1
if exist "%PIDFILE%" del /q "%PIDFILE%"
echo gway-epaper stopped
exit /b 0

:restart
call :stop
if errorlevel 1 exit /b %ERRORLEVEL%
goto :start

:status
call :is_running
if errorlevel 1 (
    if exist "%PIDFILE%" del /q "%PIDFILE%"
    echo gway-epaper stopped
    exit /b 1
)
echo gway-epaper running ^(pid !EPAPER_PID!^)
exit /b 0

:run
set "EPAPER_CONFIG_PATH=%EPAPER_CONFIG%"
pushd "%ROOT%"
"%PYTHON%" -c "from gway_epaper.runtime import run_forever; import os; run_forever(os.environ['EPAPER_CONFIG_PATH'])"
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%

:usage
echo usage: %~nx0 {start^|stop^|restart^|status^|run} 1>&2
exit /b 2
