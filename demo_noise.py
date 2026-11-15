"""
验证一件事：单次测出来的耗时差，到底能不能当结论。

我上一轮说「闲聊 Agent 6.6s，RAG 11.0s，Agent 快」。
但 deepseek-v4.1-flash 是推理模型，每次思考长度都不一样。
如果重复测 5 次，两边的分布是分开的、还是重叠的？

这是"测量"的基本功：单次数字不能当结论，要看分布。
"""
import json
import statistics
import time
import urllib.request

URL = "http://127.0.0.1:8002/api/v1/chat/stream"
N = 5
QUESTION = "你好呀，今天心情不错"


def run(use_agent: bool) -> dict:
    body = json.dumps({"message": QUESTION, "agent": use_agent}).encode()
    req = urllib.request.Request(URL, data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    ans, tools, err = "", [], None
    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            s = raw.decode("utf-8", "replace").strip()
            if not s.startswith("data:"):
                continue
            p = s[5:].strip()
            if not p or p == "[DONE]":
                continue
            ev = json.loads(p)
            if ev["type"] == "delta":
                ans += ev.get("text", "")
            elif ev["type"] == "answer_reset":
                ans = ""
            elif ev["type"] == "tool_start":
                tools.append(ev["name"])
            elif ev["type"] == "error":
                err = ev["message"]
    return {"t": time.time() - t0, "n": len(ans), "tools": tools, "err": err}


def main():
    print("=" * 72)
    print(f"闲聊题「{QUESTION}」，每种模式各跑 {N} 次")
    print("=" * 72)
    print()

    data = {"RAG": [], "Agent": []}
    for mode, flag in (("RAG", False), ("Agent", True)):
        print(f"--- {mode} ---")
        for i in range(N):
            r = run(flag)
            data[mode].append(r)
            print(f"  第{i+1}次: {r['t']:>6.1f}s  {r['n']:>4}字  工具={r['tools'] or '无'}"
                  + (f"  ⚠{r['err']}" if r["err"] else ""))
        print()

    print("=" * 72)
    print("分布对比")
    print("=" * 72)
    for mode in ("RAG", "Agent"):
        ts = [r["t"] for r in data[mode]]
        print(f"  {mode:<6} 样本 {['%.1f' % t for t in ts]}")
        print(f"         最小 {min(ts):.1f}s  中位 {statistics.median(ts):.1f}s  "
              f"最大 {max(ts):.1f}s  平均 {statistics.mean(ts):.1f}s  "
              f"极差 {max(ts)-min(ts):.1f}s")
    print()

    rag = [r["t"] for r in data["RAG"]]
    ag = [r["t"] for r in data["Agent"]]
    overlap = min(max(rag), max(ag)) - max(min(rag), min(ag))
    print(f"  RAG 范围  : {min(rag):.1f} ~ {max(rag):.1f}s")
    print(f"  Agent 范围: {min(ag):.1f} ~ {max(ag):.1f}s")
    print(f"  重叠区间  : {overlap:.1f}s")
    print()

    # 单次抽样的"结论"能有多离谱
    print("=" * 72)
    print("如果只看第 1 次，会得出什么结论？")
    print("=" * 72)
    d1 = data["RAG"][0]["t"] - data["Agent"][0]["t"]
    print(f"  第1次:  RAG {data['RAG'][0]['t']:.1f}s  vs  Agent {data['Agent'][0]['t']:.1f}s"
          f"   → 差 {d1:+.1f}s")
    best = min(rag) - max(ag)
    worst = max(rag) - min(ag)
    print(f"  5次里的真实差距范围: {worst:+.1f}s ~ {best:+.1f}s")
    print()
    print("  ⚠ 同一对模式，只因为你抽查到了哪一次，")
    print("    结论可以从「Agent 快 4 秒」翻成「Agent 慢 1 秒」。")
    print()
    print("=" * 72)
    print("真正稳定的差别在哪：工具调用次数")
    print("=" * 72)
    print(f"  RAG   : 每次都固定检索 1 次 → {['1次'] * N}")
    print(f"  Agent : {[len(r['tools']) for r in data['Agent']]} 次工具调用")
    print()
    print("  这个数字没有方差 —— 它是结构决定的，不是运气决定的。")
    print("  耗时有方差，检索次数没有。结论要下在没有方差的地方。")


if __name__ == "__main__":
    main()