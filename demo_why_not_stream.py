"""
题B 的证据：模型调用工具时，流式返回的到底是什么样子。

不是文字，是 JSON 碎片。用户看到的就是下面这些乱码。
"""
import json
import os

import requests
from dotenv import load_dotenv

load_dotenv(r"D:\Ai\Langchain\mycooker\.env")
KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

TOOLS = [{
    "type": "function",
    "function": {
        "name": "search_kb",
        "description": "在厨房知识库里检索食材处理、烹饪技巧、营养配比、家常菜做法。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "检索关键词"}},
            "required": ["query"],
        },
    },
}]


def line(ch="=", n=78):
    print(ch * n)


def run(question, tools=None):
    body = {
        "model": "deepseek-v4.1-flash",
        "messages": [
            {"role": "system", "content": "你是私厨助手，需要查资料时调用工具。"},
            {"role": "user", "content": question},
        ],
        "stream": True,
        "max_tokens": 3000,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"

    r = requests.post(f"{BASE}/chat/completions", headers=H, json=body,
                      stream=True, timeout=180)

    pieces = []          # 收到的 content 文字碎片
    raw_tool = []        # 收到的 tool_calls 原始碎片
    n_chunk = 0
    for raw in r.iter_lines():
        if not raw:
            continue
        text = raw.decode("utf-8", "replace")
        if not text.startswith("data:"):
            continue
        payload = text[5:].strip()
        if payload == "[DONE]":
            break
        try:
            data = json.loads(payload)
        except Exception:
            continue
        n_chunk += 1
        for ch in data.get("choices") or []:
            d = ch.get("delta") or {}
            if d.get("content"):
                pieces.append(d["content"])
            for tc in d.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_tool.append({
                    "index": tc.get("index"),
                    "id": tc.get("id"),
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments"),
                })
    return n_chunk, pieces, raw_tool


print()
line()
print("场景一：不需要工具（纯聊天）—— 流式很自然")
line()
n, pieces, tools_raw = run("你好，随便聊聊")
print(f"  收到 {n} 个 SSE 片段，逐个 delta.content 拼起来：")
print(f"  {''.join(pieces)[:90]!r}")
print(f"  → 用户看到的是连续输出的文字，体验正常 ✔")
print(f"  → tool_calls 片段数：{len(tools_raw)}")

print()
line()
print("场景二：需要工具 —— 如果直接流式给用户，会看到什么")
line()
n, pieces, tools_raw = run("糖醋汁的番茄酱和糖是什么比例？", TOOLS)
print(f"  收到 {n} 个 SSE 片段")
print(f"  delta.content 拼起来：{''.join(pieces)!r}   ← 空的！正文一个字都没有")
print()
print(f"  但 tool_calls 收到了 {len(tools_raw)} 个碎片：")
for i, t in enumerate(tools_raw[:14], 1):
    print(f"    {i:2}. index={t['index']}  id={str(t['id'])[:22]!r}")
    print(f"        name      = {t['name']!r}")
    print(f"        arguments = {t['arguments']!r}")
if len(tools_raw) > 14:
    print(f"    ... 还有 {len(tools_raw)-14} 个碎片")

# 拼装
name = "".join(t["name"] or "" for t in tools_raw)
args = "".join(t["arguments"] or "" for t in tools_raw)
call_id = next((t["id"] for t in tools_raw if t["id"]), None)
print()
print(f"  必须全部收完才能拼出完整调用：")
print(f"    name      = {name!r}")
print(f"    arguments = {args!r}")
print(f"    id        = {call_id!r}")

print()
line()
print("所以：如果把这堆东西原样流给用户，屏幕上会滚动这些")
line()
buf = ""
for t in tools_raw[:8]:
    if t["arguments"]:
        buf += t["arguments"]
    print(f"    {t['arguments']!r}")
print()
print(f"  用户视角：一串残破的 JSON —— {{\"quer   、y\": \"糖醋  、汁...")
print(f"  这根本不是给用户读的东西。")
print()
line()
print("结论")
line()
print("""
  工具调用返回的是【结构化 JSON 碎片】，不是给人看的文字：

  1. 是碎片，不是完整句子
     arguments 被切成 '{"quer'、'y": "糖醋'、'汁比例"}' 这样一段段推过来。
     必须全部收完再拼起来，才能得到合法的 JSON。

  2. 收完之前根本无法执行
     你没法"边收边执行"——参数还没到齐，执行什么？
     所以流式对工具调用没有任何加速作用。

  3. 内容不是给用户看的
     用户关心"番茄酱和糖几比几"，不关心内部是 search_kb 还是 database_query。
     把过程吐出来只会刷屏、让人困惑。

  4. 正文内容是空的
     模型这一轮只输出了工具调用，delta.content 一个字都没有。
     前端如果只显示内容，用户会看到一片空白（这就是之前"没有收到内容"的另一种成因）。

  正确做法：
     中间过程不流式，只给一句人话状态：「正在查资料…」「正在计算…」
     最后答案才真正流式输出。
     —— 用户看到的是"进度 + 结果"，不是"过程 + 结果"。
""")