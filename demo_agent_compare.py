"""
Agent 模式的验收：同一批问题跑两种模式，把差别量出来。

这是在证明「Agent 版更好」，不是在感受它更好。
指标只有三个，都能数：
    1. 工具调用次数
    2. 有没有给出具体数字
    3. 耗时
"""
import json
import time
import urllib.request

from _demo_util import Cleanup, note

BASE = "http://127.0.0.1:8002/api/v1/chat/stream"

QUESTIONS = [
    ("闲聊", "你好呀，今天心情不错"),
    ("单跳", "糖醋汁的番茄酱和糖是什么比例？"),
    ("多跳", "我想做红烧肉，按知识库的用量算，这一锅多少热量？一人份又是多少？"),
    ("精确", "知识库里有哪几道菜？红烧肉的用料列一下"),
    ("拒答", "糖醋排骨怎么做？"),
]


def run(question, use_agent: bool) -> dict:
    body = json.dumps({
        "message": question,
        "conversation_id": None,
        "agent": use_agent,
    }).encode()
    req = urllib.request.Request(BASE, data=body,
                                 headers={"Content-Type": "application/json"})

    t0 = time.time()
    types, ans, tools, err = [], "", [], None
    sources_n = 0
    agent_stats = None

    with urllib.request.urlopen(req, timeout=300) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if not payload or payload == "[DONE]":
                continue
            ev = json.loads(payload)
            note(ev)                  # 记下新建的会话，结束时统一删掉
            t = ev["type"]
            if t not in types:
                types.append(t)
            if t == "delta":
                ans += ev.get("text", "")
            elif t == "answer_reset":
                # 模型一边说话一边决定调工具，前面吐的那半句要丢掉。
                # 不处理这个事件，拼出来的答案会和真正存进数据库的不一样。
                ans = ""
            elif t == "tool_start":
                tools.append(ev.get("name"))
            elif t == "sources":
                sources_n = len(ev.get("sources") or [])
            elif t == "error":
                err = ev.get("message")
            elif t == "done":
                agent_stats = ev.get("agent")

    return {
        "elapsed": round(time.time() - t0, 1),
        "answer": ans or (err or ""),
        "tools": tools,
        "sources": sources_n,
        "types": types,
        "agent": agent_stats,
        "error": err,
    }


def has_number(text: str) -> bool:
    """答里有没有出现具体数字（千卡/克）。"""
    import re
    return bool(re.search(r"\d+\s*(千卡|大卡|kcal|克)", text))


def line(ch="=", n=96):
    print(ch * n)


def retrieval_count(mode: str, tools: list[str]) -> str:
    """RAG 模式不产生 tool_start 事件，但它内部固定检索了一次。
    这里把两边的"实际查了几次"对齐，否则数字会误导。"""
    if mode == "RAG":
        return "固定检索×1"
    if not tools:
        return "0 次"
    return f"{len(tools)} 次: " + ",".join(tools)


def main():
    line()
    print(f"{'问题':<10}{'模式':<8}{'实际查了几次':<44}{'数字':<6}{'资料':<6}{'耗时':<8}{'字数':<7}")
    line()

    rows = []
    for tag, q in QUESTIONS:
        for mode, use_agent in (("RAG", False), ("Agent", True)):
            try:
                r = run(q, use_agent)
            except Exception as e:
                print(f"{tag:<10}{mode:<8}✘ 请求失败: {e}")
                continue
            tools = retrieval_count(mode, r["tools"])
            num = "✔" if has_number(r["answer"]) else "—"
            print(f"{tag:<10}{mode:<8}{tools:<44}{num:<6}{r['sources']:<6}{r['elapsed']:<8}{len(r['answer']):<7}")
            rows.append((tag, mode, q, r))

        print("-" * 96)

    line()
    print("逐题答案对照")
    line()
    for tag, mode, q, r in rows:
        line("-")
        print(f"【{tag} / {mode}】{q}")
        print(f"  工具: {r['tools'] or '(无)'}   耗时 {r['elapsed']}s   资料 {r['sources']} 条")
        if r["error"]:
            print(f"  ⚠ 错误: {r['error'][:200]}")
        body = (r["answer"] or "").strip()
        # 只打前 8 行非空
        shown = 0
        for ln in body.splitlines():
            if ln.strip():
                print(f"  {ln.strip()[:110]}")
                shown += 1
                if shown >= 8:
                    break
    print()

    line()
    print("汇总")
    line()
    for mode in ("RAG", "Agent"):
        sel = [r for (t, m, q, r) in rows if m == mode]
        if not sel:
            continue
        tot_tools = sum(len(r["tools"]) for r in sel)
        avg_t = sum(r["elapsed"] for r in sel) / len(sel)
        withnum = sum(1 for r in sel if has_number(r["answer"]))
        print(f"  {mode:<7} 工具调用总计 {tot_tools:>3} 次 | 平均耗时 {avg_t:>5.1f}s | 给出具体数字 {withnum}/{len(sel)} 题")

    print()
    line()
    print("""  怎么看这张表：

  · 闲聊：Agent 应该是 0 次工具调用，RAG 固定 1 次检索 —— 这是省下来的浪费
  · 多跳：Agent 会连续调 get_dish + calc_nutrition，RAG 只有一次检索，
          给不出精确数字（它只会说"知识库没有"或者估个范围）
  · 拒答：两边都应该如实说没有，不能编 —— 这是诚实性，不能牺牲
  · 代价：Agent 的工具调用更多、耗时更长。变贵是正常的，要说清贵在哪。
""")


if __name__ == "__main__":
    with Cleanup():      # 跑完自动删掉本轮新建的测试会话
        main()