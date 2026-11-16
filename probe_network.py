"""探一下现在网络健不健康，再决定要不要花时间跑长实验。

两件事各测 5 次：
  ① 向量化（直连，已绕开系统代理）
  ② 模型最短请求（max_tokens=20）

判断标准：如果极差超过中位数的 2 倍，说明还在抽风，长实验的结论不可信。
"""
import asyncio
import statistics
import sys
import time

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")

import config
from rag import embeddings, pipeline


async def probe_model(n=5):
    client = pipeline._get_client()
    ts = []
    for i in range(n):
        t = time.time()
        r = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=[{"role": "user", "content": "说一个词"}],
            max_tokens=20, stream=False)
        el = time.time() - t
        ts.append(el)
        print(f"    第{i + 1}次 {el:>6.2f}s  output={r.usage.completion_tokens}")
    return ts


def probe_embedding(n=5):
    ts = []
    for i in range(n):
        t = time.time()
        embeddings.embed_query("糖醋汁比例")
        el = time.time() - t
        ts.append(el)
        print(f"    第{i + 1}次 {el:>6.2f}s")
    return ts


def verdict(name, ts):
    med = statistics.median(ts)
    spread = max(ts) - min(ts)
    ok = spread <= med * 2
    print(f"  {name}: 中位 {med:.2f}s  极差 {spread:.2f}s  "
          f"{'✔ 稳定' if ok else '✘ 还在抽风'}")
    return ok


async def main():
    print("=" * 66)
    print("网络健康探针")
    print(f"  绕代理: {not config.USE_SYSTEM_PROXY}   向量超时: {config.EMBEDDING_TIMEOUT}s")
    print("=" * 66)

    print("\n[1] 向量化")
    e = probe_embedding()
    ok1 = verdict("向量化", e)

    print("\n[2] 模型（最短请求）")
    m = await probe_model()
    ok2 = verdict("模型  ", m)

    print("\n" + "=" * 66)
    if ok1 and ok2:
        print("  结论：网络稳定，可以跑长实验")
        return 0
    print("  结论：网络仍不稳，别跑长实验 —— 跑出来的秒数没有意义")
    print("        可以只跑规则类验证（test_router.py，不联网）")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))