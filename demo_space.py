"""
为什么不能只记「1 - distance」：换个距离公式就不成立。

同一批向量，放进两个 collection：
    cosine 空间 → 1 - distance == cos
    l2 空间     → 1 - distance != cos   （差得很远）
"""
import shutil
import sys
import tempfile

import chromadb
import numpy as np

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")
from rag import embeddings  # noqa: E402


def line(ch="=", n=76):
    print(ch * n)


Q = "糖醋汁的比例是多少"
DOCS = [
    "糖醋汁：番茄酱 3 勺、糖 2 勺、醋 2 勺、清水 3 勺",
    "鸡蛋保存要冷藏，放冰箱中下层",
    "红烧肉要焯水去腥，小火慢炖一小时",
]

qv = np.array(embeddings.embed_query(Q), dtype=float)
vecs = [np.array(v, dtype=float) for v in embeddings.embed_documents(DOCS)]

# 真实 cos（自己手算，唯一可信的标准答案）
def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


truth = [cos(qv, v) for v in vecs]

print()
line()
print("标准答案：手算的余弦相似度（唯一真相）")
line()
for d, c in zip(DOCS, truth):
    print(f"  cos={c:.6f}   {d[:28]}")

tmp = tempfile.mkdtemp(prefix="space-demo-")
try:
    client = chromadb.PersistentClient(path=tmp)

    for space in ("cosine", "l2", "ip"):
        name = f"demo_{space}"
        col = client.create_collection(
            name=name, metadata={"hnsw:space": space}
        )
        col.add(
            ids=[f"d{i}" for i in range(len(DOCS))],
            embeddings=[v.tolist() for v in vecs],
            documents=DOCS,
            metadatas=[{"label": d[:20]} for d in DOCS],
        )
        res = col.query(query_embeddings=[qv.tolist()], n_results=len(DOCS),
                        include=["distances", "metadatas"])
        dists = res["distances"][0]
        metas = res["metadatas"][0]

        print()
        line()
        print(f"hnsw:space = {space}")
        line()
        print(f"  {'Chroma(按相关性排好序)':<26}{'distance':>11}{'1-distance':>13}{'真cos':>10}{'1-dist=cos?':>13}")
        print("  " + "-" * 71)
        for dist, meta in zip(dists, metas):
            lab = meta.get("label", "")
            # 找到它原始下标
            idx = next((i for i, d in enumerate(DOCS) if d.startswith(lab[:18])), None)
            if idx is None:
                continue
            one_minus = 1 - dist
            ok = "✔ 对" if abs(one_minus - truth[idx]) < 0.01 else "✘ 错"
            print(f"  {lab:<26}{dist:>11.6f}{one_minus:>13.6f}{truth[idx]:>10.6f}{ok:>13}")

        # 换个假设：如果是 l2，正确还原公式是什么？
        if space == "l2":
            print()
            print("  >>> l2 空间下 distance 是【欧氏距离的平方】")
            print("      单位向量时：||a-b||² = 2 - 2cos  →  cos = 1 - distance/2")
            print(f"      {'label':<26}{'1-dist/2':>12}{'真cos':>10}{'对吗':>8}")
            print("      " + "-" * 56)
            for dist, meta in zip(dists, metas):
                lab = meta.get("label", "")
                idx = next((i for i, d in enumerate(DOCS) if d.startswith(lab[:18])), None)
                if idx is None:
                    continue
                fixed = 1 - dist / 2
                ok = "✔" if abs(fixed - truth[idx]) < 0.01 else "✘"
                print(f"      {lab:<26}{fixed:>12.6f}{truth[idx]:>10.6f}{ok:>8}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print()
line()
print("结论")
line()
print("""
  1. 三个空间返回的 distance 数值完全不同，但【排序结果一样】——
     因为都在衡量"有多像"，只是度量方式不同。

  2. 只有 cosine 空间下，similarity = 1 - distance。
     l2 空间下 1 - distance 是错的，正确答案是 1 - distance/2。
     ip  空间下又是另一个公式。

  3. 所以我们不该记「1 - distance」，该记两件事：
       ① 向量库给的一定是 distance，永远是【越小越近】
       ② 我们主动设了 hnsw:space="cosine"，所以才能用 1 - distance
     第②条一变，第①条的换算公式就得跟着变。

  换句人话：
    「距离越小越近」是通用规律 —— 记这个。
    「1 减一下就是相似度」是 cosine 的巧合 —— 要连带条件一起记。
""")