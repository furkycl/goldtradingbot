@echo off
REM Runs the bot and restarts it if it ever exits (e.g. MT5 terminal restart).
REM Stop with Ctrl+C twice. Keep the MetaTrader 5 terminal open and logged in.
cd /d "%~dp0\..\.."
call .venv\Scripts\activate.bat
:loop
python -m goldbot run
echo goldbot exited with code %errorlevel%, restarting in 30 seconds...
timeout /t 30 /nobreak >nul
goto loop
