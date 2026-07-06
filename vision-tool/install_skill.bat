@echo off
chcp 65001 >nul
echo ============================================
echo   🖼️  视觉分析 Skill 安装工具
echo   将 vision-analyzer 复制到当前项目
echo ============================================
echo.

set SOURCE=D:\AI游戏\搭建废土战歌文字游戏\.trae\skills\vision-analyzer
set TARGET=.trae\skills\vision-analyzer

if not exist ".trae\skills" (
    mkdir ".trae\skills"
    echo 📁 已创建 .trae\skills 目录
)

if exist "%TARGET%" (
    echo ⚠️  当前项目已有 vision-analyzer skill
    echo    覆盖更新中...
)

xcopy "%SOURCE%" "%TARGET%" /E /I /Y >nul

echo ✅ 安装成功！
echo.
echo 现在在此项目的 Trae 对话中，你可以说：
echo   "帮我分析这张图 D:\图片.jpg"
echo   "检查这个头像质量怎么样"
echo   "提取这张图里的文字"
echo.
echo 或者直接运行脚本：
echo   python D:\AI游戏\搭建废土战歌文字游戏\vision-tool\vision_tool.py 图片路径
echo.
pause
