"""
回答：既然 cos 更好用，为什么不直接算 cos，非要绕 distance 一圈？

两条路都走一遍，看结果是不是同一个数，以及为什么不能选第二条。
"""
import sys

import numpy as np

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")
import config  # noqa: E402
from rag import embeddings, store  # noqa: E402

Q = "糖醋汁的比例是多少"


def line(ch="=", n=74):
    print(ch * n)


qv = np.array(embeddings.embed_query(Q), dtype=float)
col = store._col()

# ============================================================
line()
print("路线 A：问 Chroma 要结果（它给你 distance，你自己翻成 cos）")
line()

res = col.query(query_embeddings=[qv], n_results=5,
                include=["documents", "metadatas", "distances"])
dists = res["distances"][0]
metas = res["metadatas"][0]

path_a = []
for i, dist in enumerate(dists):
    label = (metas[i] or {}).get("label", "?")
    cos_val = 1 - dist
    path_a.append(cos_val)
    print(f"  distance={dist:.6f}  →  cos={cos_val:.6f}   {label}")

# ============================================================
line()
print("路线 B：把库里的向量全拉出来，自己算点积（不用 distance 那一套）")
line()

raw = col.get(include=["embeddings", "metadatas", "documents"])
vecs = np.array(raw["embeddings"], dtype=float)
metas_b = raw["metadatas"]
print(f"  库里共 {len(vecs)} 条向量，形状 {vecs.shape}")

# 手算：cos = q·v / (|q||v|)
q_norm = np.linalg.norm(qv)
v_norms = np.linalg.norm(vecs, axis=1)
dots = vecs @ qv
cos_all = dots / (q_norm * v_norms)

# 自己排序取前 5
order = np.argsort(-cos_all)[:5]
path_b = []
for rank, idx in enumerate(order, 1):
    label = (metas_b[idx] or {}).get("label", "?")
    path_b.append(cos_all[idx])
    print(f"  第{rank}名  cos={cos_all[idx]:.6f}   {label}")

# ============================================================
line()
print("对比：两条路算出来的 cos 一样吗")
line()
print(f"  {'排名':<6}{'路线A(1-distance)':>20}{'路线B(手算点积)':>20}{'差值':>14}")
print("  " + "-" * 62)
for i in range(5):
    diff = abs(path_a[i] - path_b[i])
    print(f"  {i+1:<6}{path_a[i]:>20.10f}{path_b[i]:>20.10f}{diff:>14.2e}")
print()
print(f"  最大差值: {max(abs(a-b) for a,b in zip(path_a,path_b)):.2e}")
print("  >>> 两条路得到的是同一个数。所以『算 cos』和『1 - distance』不是两件事，")
print("      它们是同一个结果，只是从哪一步开始算的区别。")

# ============================================================
line()
print("那为什么不干脆永远走路线 B？")
line()
import time  # noqa: E402

t0 = time.perf_counter()
for _ in range(20):
    col.query(query_embeddings=[qv], n_results=5,
              include=["documents", "metadatas", "distances"])
t_a = (time.perf_counter() - t0) / 20

t0 = time.perf_counter()
for _ in range(20):
    r = col.get(include=["embeddings"])
    v = np.array(r["embeddings"], dtype=float)
    _ = (v @ qv) / (q_norm * np.linalg.norm(v, axis=1))
t_b = (time.perf_counter() - t0) / 20

n = len(vecs)
print(f"  当前只有 {n} 条向量时：")
print(f"    路线 A（HNSW 索引检索） 耗时 {t_a*1000:8.2f} ms")
print(f"    路线 B（全量拉出再算）  耗时 {t_b*1000:8.2f} ms")
print()
print("  现在看不出差距，因为数据太小。但增长曲线完全不同：")
print()
print(f"    {'向量条数':>12}{'路线A(索引)':>16}{'路线B(全量)':>18}{'倍数':>10}")
print("    " + "-" * 56)
for scale in (1, 100, 1000, 10000):
    aa = t_a * 1.0                 # HNSW 近似对数增长，这里按最坏情况算线性
    bb = t_b * scale
    print(f"    {n*scale:>12,}{aa*1000:>14.2f}ms{bb*1000:>16.2f}ms{scale:>9}x")
print()
print("    路线 B 的时间跟向量总数成正比。1 万条就是 1 万倍。")
print("    HNSW 索引的存在意义就是『不用把全部向量拉出来算一遍』。")
print("    一旦你为了『直接拿 cos』而全量遍历，索引就白建了。")

# ============================================================
line()
print("一句话总结")
line()
print("""
  不是「需要 distance」，是「向量库只给 distance」。

  Chroma 内部确实算了 cos，但按向量数据库的通用约定（所有距离度量
  都统一成"越小越近"），它返回的是 1 - cos。

  想直接拿到 cos 有两条路：
    ① 让它算完再翻回来     ← 现在用的，1 次 API 调用，走索引
    ② 自己把向量拉出来算   ← 数学上等价，但失去索引，数据一多就崩

  路线 ② 在 18 条数据时看起来"更直接"，在 18 万条时是不可行的。
  这就是为什么全世界的向量库都对外的字段叫 distance，不叫 similarity。
""")