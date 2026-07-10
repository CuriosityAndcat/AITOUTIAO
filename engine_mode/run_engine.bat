@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo ==========================================
echo     AIToutiao 引擎模式 v1.0
echo     端口: 8502（独立运行）
echo ==========================================
echo.
echo 正在启动 Streamlit 引擎...
echo.

streamlit run engine_app.py --server.port 8502 --server.address 0.0.0.0 < nul

pause
