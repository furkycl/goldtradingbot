@echo off
REM One-time setup on Windows (needed for MetaTrader 5).
cd /d "%~dp0\..\.."
where python >nul 2>nul || (echo Install Python 3.12 from python.org first & exit /b 1)
python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt MetaTrader5 telethon
if not exist .env copy .env.example .env
python -m pytest -q
echo.
echo Setup done. Edit .env (MT5_LOGIN/MT5_PASSWORD/MT5_SERVER) and config\settings.yaml, then run scripts\windows\run.bat
