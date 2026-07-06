@echo off
chcp 65001 >nul
title AIToutiao 完整性测试
cd /d "%~dp0"

echo ========================================
echo   AIToutiao 完整性测试套件
echo ========================================
echo.

python -m pytest tests/ -v --tb=short --timeout=60 2>&1

echo.
echo ========================================
echo   测试完成
echo ========================================
pause
