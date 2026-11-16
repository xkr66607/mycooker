"""临时起一个服务、跑一个脚本、然后无论如何都把服务关掉。

解决什么问题：
  以前是「后台开服务 → 手动跑测试 → 忘了关」，于是 8002 端口一直挂着，
  用户看到端口被占，只能自己去杀掉。这个脚本让「开着」这件事不可能越过一次命令。

用法：
  python _with_server.py demo_singlehop.py
  python _with_server.py test_router.py          # 不需要服务的脚本也能用
  python _with_server.py --port 8010 -- demo_router.py

保证：
  · 跑完 / 报错 / Ctrl+C / 测试失败，都会走 finally 关掉服务
  · 关之前先 terminate（让它自己收尾），10 秒还不退才 kill
  · 起服务前如果端口已经被别人占着，先报错退出，不会去动别人的进程
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / "venv" / "Scripts" / "python.exe"
APP = ROOT / "run_app.py"


def port_busy(port: int) -> bool:
    """端口上有没有人在 listen。用净连自己判断，不依赖 Windows 命令。"""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def wait_ready(port: int, timeout: float = 60.0) -> bool:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.4)
    return False


def stop(proc: subprocess.Popen, port: int) -> None:
    """先礼后兵地关掉服务，并确认端口真的释放了。"""
    if proc.poll() is not None:
        return
    proc.terminate()                      # Windows 上等于 TerminateProcess
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print("  [with_server] 服务 10 秒没退，强制结束", file=sys.stderr)
        proc.kill()
        proc.wait(timeout=10)

    for _ in range(20):                   # 最多再等 2 秒确认端口放开
        if not port_busy(port):
            return
        time.sleep(0.1)
    print(f"  [with_server] 警告：{port} 端口似乎还占着", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8002)
    ap.add_argument("script", nargs="+", help="要跑的脚本（可以有多个）")
    args = ap.parse_args()
    port = args.port

    if port_busy(port):
        print(f"  [with_server] {port} 端口已被占用。")
        print("  先确认是谁占的，不要盲目杀：")
        print(f"    Get-NetTCPConnection -LocalPort {port} -State Listen | "
              "Select-Object OwningProcess")
        return 2

    print(f"  [with_server] 启动服务，端口 {port} …")
    env = {**__import__("os").environ, "MYCOOKER_PORT": str(port)}
    proc = subprocess.Popen(
        [str(PY), "-X", "utf8", str(APP)],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL,       # 服务的访问日志淹没测试输出，不看
        stderr=subprocess.DEVNULL,
    )

    try:
        if not wait_ready(port):
            print("  [with_server] 服务 60 秒内没起来，放弃", file=sys.stderr)
            return 3
        print(f"  [with_server] 就绪，开始跑测试")
        print()

        rc = 0
        for script in args.script:
            path = ROOT / script
            if not path.exists():
                print(f"  [with_server] 找不到脚本: {path}", file=sys.stderr)
                rc = 1
                continue
            print(f"  [with_server] ▶ {script}")
            env2 = {**env, "MYCOOKER_PORT": str(port)}
            child = subprocess.run([str(PY), "-X", "utf8", str(path)],
                                   cwd=str(ROOT), env=env2)
            if child.returncode != 0:
                rc = child.returncode
            print()
        return rc
    except KeyboardInterrupt:
        print("\n  [with_server] 收到 Ctrl+C", file=sys.stderr)
        return 130
    finally:
        print("  [with_server] 关闭服务 …")
        stop(proc, port)
        print(f"  [with_server] {port} 端口{'仍被占用' if port_busy(port) else '已释放'}")


if __name__ == "__main__":
    raise SystemExit(main())