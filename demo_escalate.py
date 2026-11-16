"""验收：检索一条都没命中时，用户得到的是不是有用的回答。

原来的设想是"自动升级到 Agent 再找一次"。实测（就是这个脚本的前一个版本）
发现那样没价值：Agent 面对同一个知识库同样查不到，对「量子力学」这类问题
它连工具都不调，直接说"这不是厨房问题"。而这件事 RAG 一样能做，还更便宜。

所以改成：0 命中时把「知识库里到底有什么」告诉用户，让他自己换问法。
查本地 Chroma，不花网络往返。

本脚本验三件事：
  1. 0 命中 → 回答里确实带了知识库清单（而不是干巴巴一句"没有"）
  2. 有命中 → 清单不会泄漏进正常回答
  3. agent=false 时走的是同一条路（对比实验不能被偷偷改道）

如果服务端开了 MYCOOKER_RAG_ESCALATE=1，会额外检查升级链路。
"""
import json
import sys
import time
import urllib.request

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")
from _demo_util import Cleanup, note

BASE = "http://127.0.0.1:8002"
URL = f"{BASE}/api/v1/chat/stream"

ZERO_HIT = "量子力学的波函数坍缩是什么意思？"   # 实测 0 命中
HIT = "糖醋汁的番茄酱和糖是什么比例？"          # 实测 5 条命中

# 知识库里 6 道菜的名字，回答里出现任意两个就算提到了清单
DISHES = ["西红柿炒鸡蛋", "宫保鸡丁", "红烧肉", "清蒸鲈鱼", "手撕包菜", "番茄牛腩"]


def escalated_on() -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/api/health", timeout=10) as r:
            return bool(json.loads(r.read()).get("rag_escalate", False))
    except Exception:
        return False


def run(q, agent_flag=None):
    body = {"message": q}
    if agent_flag is not None:
        body["agent"] = agent_flag
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    routes, notes, tools, ans, cids, err = [], [], [], "", [], None
    with urllib.request.urlopen(req, timeout=400) as r:
        for raw in r:
            s = raw.decode("utf-8", "replace").strip()
            if not s.startswith("data:"):
                continue
            p = s[5:].strip()
            if not p or p == "[DONE]":
                continue
            ev = json.loads(p)
            note(ev)
            t = ev.get("type")
            if t == "route":
                routes.append(ev.get("mode"))
            elif t == "note":
                notes.append(ev.get("text"))
            elif t == "conversation":
                cids.append(ev.get("id"))
            elif t == "tool_start":
                tools.append(ev.get("name"))
            elif t == "delta":
                ans += ev.get("text", "")
            elif t == "answer_reset":
                ans = ""
            elif t == "error":
                err = ev.get("message")
    return {"t": time.time() - t0, "routes": routes, "notes": notes,
            "tools": tools, "ans": ans, "cids": cids, "err": err}


def dishes_in(text: str) -> list[str]:
    return [d for d in DISHES if d in text]


def main():
    esc = escalated_on()
    print("=" * 88)
    print("0 命中时的回答质量验收")
    print(f"  自动升级: {'开' if esc else '关（默认）'}")
    print("=" * 88)
    print()

    with Cleanup():
        print(f"[1] 0 命中题：{ZERO_HIT}")
        r1 = run(ZERO_HIT)
        found = dishes_in(r1["ans"])
        print(f"    route 事件   : {r1['routes']}")
        print(f"    note 提示    : {r1['notes']}")
        print(f"    工具调用     : {r1['tools']}")
        print(f"    会话 id      : {len(set(r1['cids']))} 个")
        print(f"    回答长度     : {len(r1['ans'])} 字   耗时 {r1['t']:.1f}s")
        print(f"    提到的菜     : {found or '（一个都没提）'}")
        print(f"    回答开头     : {r1['ans'][:100].replace(chr(10), ' ')}")
        if r1["err"]:
            print(f"    ⚠ 错误: {r1['err']}")
        print()

        print(f"[2] 有命中题：{HIT}（清单不该出现在这里）")
        r2 = run(HIT)
        leak = dishes_in(r2["ans"])
        print(f"    route 事件   : {r2['routes']}")
        print(f"    回答长度     : {len(r2['ans'])} 字   耗时 {r2['t']:.1f}s")
        print(f"    说的菜       : {leak or '（没提清单，正确）'}")
        print(f"    回答开头     : {r2['ans'][:70].replace(chr(10), ' ')}")
        print()

        print(f"[3] 强制 RAG（agent=false），应和 [1] 走同一条路")
        r3 = run(ZERO_HIT, agent_flag=False)
        print(f"    route 事件   : {r3['routes']}")
        print(f"    会话 id      : {len(set(r3['cids']))} 个")
        if r3["err"]:
            print(f"    ⚠ 错误: {r3['err']}")
        print()

        print("=" * 88)
        checks = [
            ("0 命中时路由判成 rag", r1["routes"][:1] == ["rag"]),
            ("0 命中时提到了知识库里的菜", len(found) >= 2),
            ("有命中时不泄漏清单", len(leak) < 2),
            ("每次提问只产生一个会话", len(set(r1["cids"])) == 1 and len(set(r3["cids"])) == 1),
            ("没有报错", not (r1["err"] or r2["err"] or r3["err"])),
        ]
        if esc:
            checks.append(("升级链路生效", r1["routes"][1:] == ["agent"]))
        else:
            checks.append(("默认不升级", r1["routes"] == ["rag"]))

        ok = 0
        for name, passed in checks:
            print(f"  {'✔' if passed else '✘'} {name}")
            ok += passed
        print(f"  {ok}/{len(checks)} 通过")
        print("=" * 88)
        return 0 if ok == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())