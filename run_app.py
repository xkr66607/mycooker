"""
一键启动：拉起服务 + 自动打开浏览器。

直接运行：
    venv\\Scripts\\python.exe run_app.py
"""
from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# 优先用项目自带 venv 的 python，避免装错环境
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"


def _open_browser_later(url: str, delay: float = 2.5) -> None:
    def _job():
        time.sleep(delay)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    threading.Thread(target=_job, daemon=True).start()


def main() -> None:
    import config  # 延迟导入，确保 sys.path 已就绪

    url = f"http://{config.HOST}:{config.PORT}/"

    print("=" * 58)
    print("  私厨 AI 助手 · RAG 版")
    print("=" * 58)
    print(f"  界面地址 : {url}")
    print(f"  对话模型 : {config.CHAT_MODEL}")
    print(f"  向量模型 : {config.EMBEDDING_MODEL} ({config.EMBEDDING_DIM} 维)")
    print(f"  知识库   : {config.CHROMA_DIR}")
    print(f"  会话库   : {config.DB_PATH}")

    missing = config.assert_ready()
    if missing:
        print()
        print(f"  ⚠ 缺少配置: {', '.join(missing)}")
        print("    请检查 .env 文件后重试")
        sys.exit(1)

    print("=" * 58)
    print("  按 Ctrl+C 停止服务")
    print()

    _open_browser_later(url)

    import uvicorn

    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()