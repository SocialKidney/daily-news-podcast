@echo off
cd /d "%~dp0"
echo ===================================================
echo  DAILY BRIEFING AND PODCAST: PREVIEW MODE (DRY RUN)
echo ===================================================
echo.
python main.py --dry-run
echo.
echo ===================================================
echo  Preview complete! Check the 'output' folder for:
echo   - The podcast MP3 file
echo   - The HTML newsletter
echo   - The script text file
echo ===================================================
echo.
pause
