@echo off
cd /d "%~dp0"
set CURRENT_DIR=%~dp0
echo =========================================================
echo  REGISTERING 7:00 AM AUTOMATED WINDOWS TASK
echo =========================================================
echo.
echo Attempting to register daily task with Windows Task Scheduler...

schtasks /create /tn "DailyMorningNewsPodcast" /tr "cmd /c cd /d \"%CURRENT_DIR%\" && python main.py --run-now" /sc daily /st 07:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo =========================================================
    echo  SUCCESS! Task 'DailyMorningNewsPodcast' registered.
    echo  Windows will automatically trigger the service daily
    echo  at 7:00 AM Mountain Time in the background.
    echo =========================================================
) else (
    echo.
    echo [NOTE] If registration failed, right-click this file
    echo and choose 'Run as administrator'.
)
echo.
pause
