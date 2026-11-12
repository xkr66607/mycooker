"""
一键启动：拉起服务 + 自动打开浏览器。

直接运行：
    venv\\Scripts\\python.exe run_app.py
"""
from __future__ import annotations

import socket
import subprocess
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


def _port_owner(port: int) -> tuple[bool, str]:
    """端口是否被占，以及是谁占的。返回 (占用?, 描述)。"""
    # 1) 先试着连一下，能连上说明有人在服务
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.6)
        in_use = s.connect_ex(("127.0.0.1", port)) == 0

    if not in_use:
        return False, ""

    who = ""
    # 2) 用 netstat 查 PID（Windows 自带，不依赖第三方库）
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True, text=True, timeout=6,
            encoding="utf-8", errors="replace",
        ).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[1].endswith(f":{port}") and parts[3] == "LISTENING":
                pid = parts[4]
                name = ""
                try:
                    name = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                        capture_output=True, text=True, timeout=6,
                        encoding="utf-8", errors="replace",
                    ).stdout.strip().split(",")[0].strip('"')
                except Exception:
                    pass
                who = f"PID {pid}" + (f"（{name}）" if name else "")
                break
    except Exception:
        pass

    return True, who


def main() -> None:
    import config  # 延迟导入，确保 sys.path 已就绪

    url = f"http://{config.HOST}:{config.PORT}/"

    print("=" * 58)
    print("  私厨 AI 助手 · RAG 版")
    print("=" * 58)
    print(f"  界面地址 : {url}")
    print(f"  对话模型 : {config.CHAT_MODEL}")
    print(f"  视觉模型 : {config.VISION_MODEL}")
    print(f"  向量模型 : {config.EMBEDDING_MODEL} ({config.EMBEDDING_DIM} 维)")
    print(f"  知识库   : {config.CHROMA_DIR}")
    print(f"  会话库   : {config.DB_PATH}")

    missing = config.assert_ready()
    if missing:
        print()
        print(f"  ⚠ 缺少配置: {', '.join(missing)}")
        print("    请检查 .env 文件后重试")
        sys.exit(1)

    # 端口被占是最常见的启动失败原因，而 uvicorn 的原始报错看不懂。
    # 提前检查，直接告诉用户怎么办。
    busy, who = _port_owner(config.PORT)
    if busy:
        print()
        print("=" * 58)
        print(f"  ✘ 端口 {config.PORT} 已被占用，启动失败")
        print("=" * 58)
        print(f"  占用者：{who or '未知进程'}")
        print()
        print("  说明：已经有一个服务在跑，或者上次没关干净。")
        print()
        print(f"  情况一：那个服务就是你要用的")
        print(f"         直接打开 {url} 即可，不用再启动")
        print()
        print("  情况二：想重启，先杀掉占用者")
        pid = who.split()[1] if who.startswith("PID ") else "<PID>"
        print(f"         任务管理器 → 详细信息 → 找 PID {pid} → 结束任务")
        print("         或者在本窗口执行：")
        print(f"             taskkill /PID {pid} /F")
        print()
        print("  情况三：换个端口")
        print("         在 .env 里改 PORT=8002，再重新启动")
        print()
        sys.exit(1)

    for w in config.warnings():
        print(f"  ⚠ {w}")

    print("=" * 58)
    print("  按 Ctrl+C 停止服务")
    print()

    _open_browser_later(url)

    import uvicorn

    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False, log_level="info")


if __name__ == "__main__":
    main()