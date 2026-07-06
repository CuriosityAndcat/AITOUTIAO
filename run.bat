@echo off
chcp 65001 >nul
title AIToutiao 一键内容生成器

:: 禁用 CMD 快速编辑模式（防止点击窗口导致进程假死）
powershell -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -Name Console -Namespace Win32 -MemberDefinition '[DllImport(\"kernel32.dll\")] public static extern IntPtr GetStdHandle(int nStdHandle); [DllImport(\"kernel32.dll\")] public static extern bool GetConsoleMode(IntPtr hConsole, out uint lpMode); [DllImport(\"kernel32.dll\")] public static extern bool SetConsoleMode(IntPtr hConsole, uint dwMode);'; $h = [Win32.Console]::GetStdHandle(-10); $m = 0; [Win32.Console]::GetConsoleMode($h, [ref]$m); $m = $m -band -bnot 0x0040; [Win32.Console]::SetConsoleMode($h, $m)" 2>nul

cd /d "%~dp0"

echo ========================================
echo   AIToutiao 一键内容生成器
echo   Starting Streamlit Server...
echo ========================================
echo.

:: Check if streamlit is installed
python -c "import streamlit" 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 正在安装 Streamlit...
    pip install streamlit python-dotenv -q
    echo.
)

echo [INFO] 启动 Streamlit 服务...
echo [INFO] 浏览器将自动打开: http://127.0.0.1:8501
echo.
echo 按 Ctrl+C 可停止服务
echo ========================================
echo.

streamlit run streamlit_app.py --server.port 8501 --server.headless true --server.address 127.0.0.1

pause
