"""拆开量：闲聊走 RAG 模式时，那多出来的 5 秒到底花在哪一步。

不猜，逐段计时。
"""
import asyncio
import sys
import time

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")

import config
from memory import store as memory
from rag import agent, embeddings, pipeline, store

Q = "你好呀，今天心情不错"


async def main():
    print("=" * 74)
    print(f"拆解「{Q}」")
    print("=" * 74)
    print()

    # --- 1) 向量化 ---
    t = time.time()
    vec = embeddings.embed_query(Q)
    t_embed = time.time() - t
    print(f"  1. 向量化 embed_query      : {t_embed*1000:>7.0f} ms")

    # --- 2) Chroma 检索 ---
    t = time.time()
    hits = store.search(vec, k=config.TOP_K)
    t_search = time.time() - t
    print(f"  2. Chroma 检索              : {t_search*1000:>7.0f} ms  （命中 {len(hits)} 条）")

    # --- 3) 拼上下文 ---
    t = time.time()
    ctx = pipeline.build_context(hits) if hits else ""
    t_ctx = time.time() - t
    print(f"  3. 拼上下文                 : {t_ctx*1000:>7.0f} ms  （{len(ctx)} 字）")
    print()

    # --- 4) 两种模式的 prompt 长度对比 ---
    history = memory.get_history(memory.ensure_conversation(None, Q))
    facts = memory.get_facts() if hasattr(memory, "get_facts") else []

    rag_msgs = pipeline._messages(Q, ctx, history, facts)
    agent_msgs = [{"role": "system", "content": agent.AGENT_SYSTEM_PROMPT},
                  {"role": "user", "content": Q}]

    def chars(msgs):
        return sum(len(m.get("content") or "") for m in msgs)

    print("  4. 送进模型的 prompt 大小")
    print(f"     RAG    : {len(rag_msgs)} 条消息, {chars(rag_msgs):>6} 字")
    for m in rag_msgs:
        c = len(m.get('content') or '')
        print(f"              - {m['role']:<9} {c:>6} 字")
    print(f"     Agent  : {len(agent_msgs)} 条消息, {chars(agent_msgs):>6} 字")
    for m in agent_msgs:
        c = len(m.get('content') or '')
        print(f"              - {m['role']:<9} {c:>6} 字")
    print(f"     差值   : {chars(rag_msgs) - chars(agent_msgs):>6} 字")
    print()

    # --- 5) 实际调模型，看 input token 数 ---
    print("  5. 真调一次，看 usage（input tokens 才是决定速度的）")
    client = pipeline._get_client()
    for label, msgs, kw in [
        ("RAG  ", rag_msgs, {"tools": None}),
        ("Agent", agent_msgs, {"tools": agent.tools.TOOLS}),
    ]:
        t = time.time()
        r = await client.chat.completions.create(
            model=config.CHAT_MODEL, messages=msgs, stream=False,
            max_tokens=config.AGENT_MAX_TOKENS if "Agent" in label else config.CHAT_MAX_TOKENS,
            **kw,
        )
        el = time.time() - t
        u = r.usage
        print(f"     {label}: {el:>5.1f}s  input={u.prompt_tokens:>5}  "
              f"output={u.completion_tokens:>4}")
        det = getattr(u, "completion_tokens_details", None)
        if det is not None:
            rt = getattr(det, "reasoning_tokens", None)
            if rt is not None:
                print(f"             其中思考 {rt} tokens，正文 {u.completion_tokens - rt}")

    print()
    print("=" * 74)


if __name__ == "__main__":
    asyncio.run(main())