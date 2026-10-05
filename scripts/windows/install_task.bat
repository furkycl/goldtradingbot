@echo off
REM Start the bot automatically when you log in to Windows (Task Scheduler).
cd /d "%~dp0\..\.."
schtasks /Create /F /SC ONLOGON /RL LIMITED /TN "goldbot" /TR "\"%cd%\scripts\windows\run.bat\""
echo Task "goldbot" created. Remove with: schtasks /Delete /TN goldbot /F
