@echo off
cd /d "%~dp0"
echo ===================================================
echo  DAILY BRIEFING AND PODCAST: RUNNING TODAY'S EPISODE
echo ===================================================
echo.
python main.py --run-now
echo.
pause
