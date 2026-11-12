"""
三个问题，测出「固定检索一次」这种做法的天花板在哪。

不看代码，只看现象：
    问题1 单跳  —— 一次检索就够，应该答得好
    问题2 多跳  —— 需要"先查菜谱，再算热量"，一次检索做不到
    问题3 闲聊  —— 根本不需要检索，但现在的实现照样查 5 条
"""
import asyncio
import sys

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")

import config  # noqa: E402
from rag import pipeline, store  # noqa: E402

QUESTIONS = [
    ("单跳", "糖醋汁的比例是多少？"),
    ("多跳", "我在减肥，想吃糖醋排骨。帮我算算按知识库的做法，一顿大概多少热量、多少蛋白质？"),
    ("闲聊", "你好呀，今天想做饭但没什么灵感"),
]


def line(ch="=", n=78):
    print(ch * n)


async def probe(tag, q):
    # 先单独看检索到了什么（这是 Agent 版能改变的地方）
    hits = await pipeline.retrieve(pipeline._build_query(q, None))

    print()
    line()
    print(f"【{tag}】{q}")
    line()
    print(f"  固定检索次数: 1 次（代码写死的，模型没有选择权）")
    print(f"  命中 {len(hits)} 条：")
    for i, h in enumerate(hits[:3], 1):
        lab = h.get("label") or h.get("section") or "?"
        prev = (h.get("text") or "")[:46].replace("\n", " ")
        print(f"    {i}. [{h['similarity']:.3f}] {lab}  |  {prev}")

    # 再看模型最终怎么答
    ans, err, think = "", None, 0
    async for ev in pipeline.stream_chat(q, None, None):
        if ev["type"] == "delta":
            ans += ev.get("text", "")
        elif ev["type"] == "thinking":
            think += len(ev.get("text", ""))
        elif ev["type"] == "error":
            err = ev.get("message")

    print()
    print(f"  答案（{len(ans)} 字，思考 {think} 字）：")
    body = (err or ans).strip()
    for ln in body.splitlines():
        if ln.strip():
            print(f"    {ln.strip()[:100]}")
    print()


async def main():
    line()
    print("当前实现的流程（写死的）")
    line()
    print("""
   用户问题 ──▶ 固定检索 1 次 ──▶ 拼进上下文 ──▶ 模型生成
                    ▲
                    └── 模型在这之前没有任何决定权
                        要不要查？查几次？查什么词？全都不由它说了算
""")
    for tag, q in QUESTIONS:
        await probe(tag, q)

    line()
    print("结论（这是实测出来的，不是猜的）")
    line()
    print("""
  先说好消息：单跳问题现在答得很好，多跳问题模型也没有瞎编 ——
  它老实说了「知识库里没有排骨数据」。这是系统提示里「引用必须真实」在起作用。

  但「诚实地说不知道」不等于「解决了问题」。真正的短板有三个：

  1. 【致命】多跳问题只能拿到一半资料
     「算糖醋排骨的热量」需要两份资料：
         ① 糖醋排骨的做法（才知道放多少糖、多少油）
         ② 排骨的营养成分（才知道每 100 克多少热量）
     固定检索一次，只召回了 ②（营养数据），① 完全没出现。
     模型手上只有营养表，没有用量，算不出来，只能估算 + 声明是估算。

     关键：向量检索一次只能回答一个语义方向的问题。
     「糖醋排骨 + 热量」被压成一个向量，谁都不像，两头不讨好。

  2. 【浪费】闲聊也查 5 条，而且全是噪音
     「你好呀，今天想做饭但没什么灵感」召回了 0.457 / 0.404 / 0.402 的片段，
     没有一条真正相关。这些内容还被塞进了上下文，模型得费劲绕开它们。
     该查的时候查，不该查的时候别查 —— 这个判断只有模型能做。

  3. 【不可靠】需要算数的地方只能靠估
     「多少热量、多少蛋白质」本质是算术题。
     大模型的算术不可靠，给它一个计算函数，它才能给准确数字。

  所以 Agent 版要改的不是「检索得更好」，而是三件事：
     ① 让模型能连续查多次（先查菜谱，再查营养）
     ② 让模型自己判断要不要查（闲聊就不查）
     ③ 给模型工具去算，而不是让它心算

  一句话：把「查几次、查什么、算不算」的决定权，从代码交给模型。
""")


asyncio.run(main())