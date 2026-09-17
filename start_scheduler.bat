@echo off
cd /d "%~dp0"
echo ===================================================
echo  DAILY BRIEFING: 7:00 AM LOCAL SCHEDULER
echo ===================================================
echo.
echo This window will wait and automatically trigger every morning at 7:00 AM Mountain Time.
echo Keep this window minimized in the background.
echo (Press Ctrl+C to stop the scheduler at any time.)
echo.
python main.py --schedule
pause
