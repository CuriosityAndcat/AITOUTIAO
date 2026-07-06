@echo off
cd /d "%~dp0"
call .\venv\Scripts\activate.bat
echo 正在启动今日头条自动发布服务...
echo.
cd backend
python main.py
pause
