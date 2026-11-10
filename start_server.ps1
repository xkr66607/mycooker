# 私厨 AI 助手 · RAG 版 —— PowerShell 启动脚本
# 用法：右键「使用 PowerShell 运行」，或执行  .\start_server.ps1

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

Write-Host ""
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host "  私厨 AI 助手 · RAG 版" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor DarkGray
Write-Host ""

$py = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    Write-Host "[错误] 找不到 venv\Scripts\python.exe" -ForegroundColor Red
    Write-Host "       请先执行：" -ForegroundColor Gray
    Write-Host "           python -m venv venv" -ForegroundColor Gray
    Write-Host "           venv\Scripts\pip install -r requirements.txt" -ForegroundColor Gray
    Write-Host ""
    Read-Host "按回车退出"
    exit 1
}

Write-Host "正在启动服务，稍后会自动打开浏览器..." -ForegroundColor Cyan
Write-Host "按 Ctrl+C 可停止服务" -ForegroundColor Gray
Write-Host ""

& $py -X utf8 run_app.py

Write-Host ""
Read-Host "服务已停止，按回车退出"