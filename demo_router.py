"""
路由器验收：它到底把每道题分到了对的那条路？

对照的是已经重复测过的基线（见 demo_noise.py / demo_singlehop.py）：
    闲聊    chat 2.0s   rag 6.9s     → 该走 chat
    单跳    rag  5.8s   agent 11.8s  → 该走 rag
    多跳    agent 精确  rag 给不出   → 该走 agent

每个组合跑 2 次，取中位，避免单次噪声。
"""
import json
import statistics
import time
import urllib.request

from _demo_util import Cleanup, note

URL = "http://127.0.0.1:8002/api/v1/chat/stream"
REPEAT = 2

# (标签, 问题, 期望路线)
CASES = [
    ("闲聊", "你好呀，今天心情不错", "chat"),
    ("单跳", "糖醋汁的番茄酱和糖是什么比例？", "rag"),
    ("复杂", "我想做红烧肉，按知识库的用量算，这一锅多少热量？一人份又是多少？", "agent"),
]


def run(q: str, agent_flag):
    body = {"message": q}
    if agent_flag is not None:
        body["agent"] = agent_flag
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    ans, route, tools, err, agent_stats = "", None, [], None, None
    with urllib.request.urlopen(req, timeout=400) as r:
        for raw in r:
            s = raw.decode("utf-8", "replace").strip()
            if not s.startswith("data:"):
                continue
            p = s[5:].strip()
            if not p or p == "[DONE]":
                continue
            ev = json.loads(p)
            note(ev)                  # 记下新建的会话，结束时统一删掉
            t = ev["type"]
            if t == "route":
                route = ev
            elif t == "delta":
                ans += ev.get("text", "")
            elif t == "answer_reset":
                ans = ""
            elif t == "tool_start":
                tools.append(ev["name"])
            elif t == "error":
                err = ev["message"]
            elif t == "done":
                agent_stats = ev.get("agent")
    return {"t": time.time() - t0, "ans": ans, "route": route,
            "tools": tools, "err": err, "ag": agent_stats}


def main():
    print("=" * 96)
    print("路由器验收")
    print("=" * 96)
    print()

    results = []
    for tag, q, want in CASES:
        print(f"【{tag}】{q}")
        for flag, label in ((None, "路由"), (False, "强制RAG"), (True, "强制Agent")):
            ts, info = [], {}
            for _ in range(REPEAT):
                try:
                    r = run(q, flag)
                except Exception as e:
                    print(f"    {label:<10} ✘ {e}")
                    continue
                ts.append(r["t"])
                info = r
            if not ts:
                continue
            med = statistics.median(ts)
            if flag is None:
                got = (info.get("route") or {}).get("mode")
                why = (info.get("route") or {}).get("reason", "")
                mark = "✔" if got == want else "✘"
                print(f"    {label:<10} {med:>6.1f}s  → 走 {got} {mark}  （{why}）")
            else:
                print(f"    {label:<10} {med:>6.1f}s  工具 {len(info['tools'])} 次"
                      + (f"  ⚠ {info['err'][:40]}" if info["err"] else ""))
            results.append((tag, label, med, info))

        print()

    # 路由 vs 两个固定模式谁更好
    print("=" * 96)
    print("路由选得对不对：和两个固定模式比")
    print("=" * 96)
    for tag, _, want in CASES:
        sel = {lbl: med for (t, lbl, med, _) in results if t == tag}
        if not sel:
            continue
        best_forced = min((v, k) for k, v in sel.items() if k != "路由")
        routed = sel.get("路由")
        win = "✔ 选到了更快/更合适的那条" if routed is not None and routed <= best_forced[0] * 1.15 \
            else "— 比最快的那条慢一点"
        print(f"  {tag:<4} 路由 {routed:>6.1f}s | 最快固定模式 {best_forced[1]}({best_forced[0]:.1f}s)   {win}")
    print()
    print("=" * 96)
    print("""  注意「强制RAG」在复杂题上的表现：它不会报错，但它给不出精确数字。
  路由的价值不是让每题都最快，而是让填空题用快路、计算题用对的路。""")
    print("=" * 96)


if __name__ == "__main__":
    with Cleanup():      # 跑完自动删掉本轮新建的测试会话
        main()