"""demo 脚本的公共收尾：别把测试会话留在用户的会话列表里。

问题：每个 demo 都发 POST /chat/stream 且 conversation_id=None，
后端会给每次提问建一个新会话。跑一轮 5 次 × 2 模式就是 10 个，
直接把侧边栏刷满，用户还得手动清。

用法（每个 demo 只要加三行）：

    from _demo_util import Cleanup, note

    with Cleanup() as cp:          # 退出时自动删掉本轮新建的会话
        ...
        for ev in stream:
            note(ev)               # 内部只在 conversation 事件时记录 id

注意：只删**本轮**新建的。如果传了 conversation_id 复用别人的会话，
就不会被记录，也就不会被删。
"""
from __future__ import annotations

import json
import urllib.request

BASE = "http://127.0.0.1:8002"

# 本轮新建的会话 id。用模块级变量是为了让 note() 不用到处传参。
_SESSIONS: list[str] = []


def note(ev: dict) -> None:
    """喂事件进来，只在新建会话时记录 id。其它事件直接忽略。"""
    if not isinstance(ev, dict):
        return
    if ev.get("type") == "conversation":
        cid = ev.get("id")
        if cid and cid not in _SESSIONS:
            _SESSIONS.append(cid)


def _delete(cid: str) -> bool:
    req = urllib.request.Request(f"{BASE}/api/v1/chat/conversations/{cid}", method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception:
        return False


class Cleanup:
    """with 块退出时删掉本轮新建的所有会话（包括异常退出）。"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.start = 0

    def __enter__(self):
        self.start = len(_SESSIONS)   # 记一个水位，只清这之后新增的
        return self

    def __exit__(self, exc_type, exc, tb):
        mine = _SESSIONS[self.start:]
        if not mine:
            if self.verbose:
                print("  （本轮没有新建会话，无需清理）")
            return False

        ok = sum(1 for cid in mine if _delete(cid))
        del _SESSIONS[self.start:]

        if self.verbose:
            mark = "✔" if ok == len(mine) else "⚠"
            print(f"  {mark} 已清理本轮测试会话 {ok}/{len(mine)} 个")
        return False   # 不吞异常


def _selftest():
    """不联网的自测：确认水位逻辑只取本轮新增的。"""
    global _SESSIONS
    _SESSIONS.clear()
    _SESSIONS.extend(["old-1", "old-2"])          # 假装之前就有的

    cp = Cleanup(verbose=False)
    cp.__enter__()
    note({"type": "conversation", "id": "new-1"})
    note({"type": "delta", "text": "无关事件"})
    note({"type": "conversation", "id": "new-2"})
    note({"type": "conversation", "id": "new-1"})  # 重复，不该加
    mine = _SESSIONS[cp.start:]

    assert mine == ["new-1", "new-2"], mine
    assert "old-1" not in mine
    print(f"  自测通过：本轮 {mine}，历史 {_SESSIONS[:2]} 不受影响")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())