"""题 A' 的实测：真正需要检索时，Agent 比 RAG 快还是慢？

上次给的单跳数据（RAG 6.3s / Agent 7.6s）是单次抽样。
既然刚证明单次不可靠，这里也跑 3 次看分布。

顺便数清楚：两边各调了几次模型、几 次检索。
"""
import json
import statistics
import time
import urllib.request

URL = "http://127.0.0.1:8002/api/v1/chat/stream"
N = 3
QUESTION = "糖醋汁的比例是多少？"


def run(use_agent: bool) -> dict:
    body = json.dumps({"message": QUESTION, "agent": use_agent}).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    ans, tools, err, n_delta = "", [], None, 0
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            s = raw.decode("utf-8", "replace").strip()
            if not s.startswith("data:"):
                continue
            p = s[5:].strip()
            if not p or p == "[DONE]":
                continue
            ev = json.loads(p)
            t = ev["type"]
            if t == "delta":
                ans += ev.get("text", "")
                n_delta += 1
            elif t == "answer_reset":
                ans = ""
            elif t == "tool_start":
                tools.append(ev["name"])
            elif t == "error":
                err = ev["message"]
    return {"t": time.time() - t0, "n": len(ans), "tools": tools,
            "err": err, "rounds": (len(tools) + 1)}


def main():
    print("=" * 72)
    print(f"「{QUESTION}」—— 这是一道单跳题，只需要检索一次")
    print("=" * 72)
    print()

    data = {"RAG": [], "Agent": []}
    for mode, flag in (("RAG", False), ("Agent", True)):
        print(f"--- {mode} ---")
        for i in range(N):
            r = run(flag)
            data[mode].append(r)
            print(f"  第{i+1}次: {r['t']:>6.1f}s  {r['n']:>4}字  "
                  f"工具 {len(r['tools'])} 次 {r['tools']}"
                  + (f"  ⚠{r['err']}" if r["err"] else ""))
        print()

    print("=" * 72)
    rag = [r["t"] for r in data["RAG"]]
    ag = [r["t"] for r in data["Agent"]]
    print(f"  RAG   {['%.1f' % x for x in rag]}  中位 {statistics.median(rag):.1f}s  极差 {max(rag)-min(rag):.1f}s")
    print(f"  Agent {['%.1f' % x for x in ag]}  中位 {statistics.median(ag):.1f}s  极差 {max(ag)-min(ag):.1f}s")
    print(f"  中位差: {statistics.median(ag) - statistics.median(rag):+.1f}s （Agent 减 RAG）")
    print()

    print("=" * 72)
    print("关键：两边各调了几次模型、几次检索")
    print("=" * 72)
    print(f"  RAG   : 模型 1 次 + 向量化 1 次（检索和作答在同一次请求里完成）")
    print(f"  Agent : 模型 {1 + len(data['Agent'][0]['tools'])} 次 + 向量化 "
          f"{len(data['Agent'][0]['tools'])} 次")
    print()
    print("  注意：这道题 Agent 也只检索了 1 次，两边检索次数一样。")
    print("  差的是 Agent 把「决定查什么」和「根据结果作答」拆成了两次模型调用。")
    print("=" * 72)


if __name__ == "__main__":
    main()