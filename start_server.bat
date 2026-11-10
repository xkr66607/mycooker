@echo off
chcp 65001 >nul
title 私厨 AI 助手 · RAG 版
cd /d "%~dp0"

echo ============================================================
echo   私厨 AI 助手 · RAG 版
echo ============================================================
echo.

if not exist "venv\Scripts\python.exe" (
    echo [错误] 找不到 venv\Scripts\python.exe
    echo        请先创建虚拟环境：
    echo            python -m venv venv
    echo            venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo 正在启动服务，稍后会自动打开浏览器...
echo 按 Ctrl+C 可停止服务
echo.

venv\Scripts\python.exe run_app.py

echo.
echo 服务已停止。
pause