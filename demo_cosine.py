"""
回答两个疑问：
  疑问1：既然 similarity 就是 cos，为什么还要算 1 - distance？
  疑问2：归一化向量 / 点积等于余弦，到底什么意思？
全部用真实数据，不用任何假设。
"""
import sys

import numpy as np

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")
import config  # noqa: E402
from rag import embeddings, store  # noqa: E402

Q = "糖醋汁的比例是多少"


def line(ch="=", n=76):
    print(ch * n)


# ============================================================
line()
print("疑问 1 之一：Chroma 到底给你返回什么？我们把原始结果挖出来看")
line()
qv = embeddings.embed_query(Q)
col = store._col()

raw = col.query(
    query_embeddings=[qv],
    n_results=5,
    include=["documents", "metadatas", "distances"],
)
dists = raw.get("distances") or [[]]
docs = raw.get("documents") or [[]]
metas = raw.get("metadatas") or [[]]

d = dists[0]
print(f"\n  问句：{Q}\n")
print(f"  {'#':<3}{'Chroma 返回的 distances':>26}{'对应文档片段':>10}")
print("  " + "-" * 70)
for i, dist in enumerate(d):
    label = (metas[0][i] or {}).get("label", "?") if metas[0] else "?"
    snippet = (docs[0][i] or "")[:34].replace("\n", " ")
    print(f"  {i+1:<3}{dist:>26.6f}   {label} | {snippet}")

print()
print("  >>> 注意：Chroma 根本没给你 cos，它给的是 distances，而且是【越小越像】。")
print("      最大的问题：如果你拿这个数当相似度直接排序，会把最不像的排到最前。")

# ------------------------------------------------------------
line("-")
print("疑问 1 之二：如果不转换，直接用 distance 排序，会发生什么")
line("-")

wrong = sorted(range(len(d)), key=lambda i: d[i], reverse=True)   # 错的写法
right = sorted(range(len(d)), key=lambda i: 1 - d[i], reverse=True)  # 对的写法

print("\n  错误写法  out.sort(key=lambda x: x['distance'], reverse=True)")
for rank, i in enumerate(wrong, 1):
    label = (metas[0][i] or {}).get("label", "?")
    print(f"     第{rank}名  distance={d[i]:.6f}   {label}")

print("\n  正确写法  out.sort(key=lambda x: x['similarity'], reverse=True)")
for rank, i in enumerate(right, 1):
    label = (metas[0][i] or {}).get("label", "?")
    print(f"     第{rank}名  similarity={1-d[i]:.6f}   {label}")

print()
print("  >>> 错误写法把最不相关的排第 1，模型拿到的第一批上下文全是不相关的。")
print("      这就是为什么必须做 1 - distance 这个转换 ——")
print("      不是因为 cos 没算出来，而是因为【Chroma 交给你的已经是另一个数了】。")

# ------------------------------------------------------------
line("-")
print("疑问 1 之三：一个类比")
line("-")
print("""
  温度计给你的是「华氏 77 度」，你要的是「摄氏 25 度」。
  你换算：C = (F - 32) / 1.8 → 25。
  换算完得到的就是「摄氏温度本身」。

  这不叫多此一举，这叫「把一个不是你想要的刻度，翻成你要的刻度」。
  同理：
      华氏 77      →  摄氏 25        （温度换算）
      distance 0.25 →  similarity 0.75  （相似度换算）
      换算结果确实"就是"摄氏温度/余弦相似度本身
      但你手上原本拿到的那个数，不是它。
""")

# ============================================================
line()
print("疑问 2：归一化向量 —— 为什么点积就等于余弦")
line()

A = np.array(embeddings.embed_query("糖醋汁的比例"), dtype=float)
B = np.array(embeddings.embed_query("番茄酱和糖各放几勺"), dtype=float)


def cos_formula(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


print(f"\n  向量 A 的长度 |A| = {np.linalg.norm(A):.10f}")
print(f"  向量 B 的长度 |B| = {np.linalg.norm(B):.10f}")
print("\n  >>> 两个长度都是 1。这就是「归一化」/「单位向量」。")

print(f"\n  cos 完整公式      = A·B / (|A| × |B|) = {cos_formula(A, B):.10f}")
print(f"  直接算点积  A·B   =                    {float(np.dot(A, B)):.10f}")
print("  >>> 分母 |A|×|B| = 1×1 = 1，除以 1 不改变任何东西，所以点积 = cos。")

# ------------------------------------------------------------
line("-")
print("疑问 2 之二：归一化的意义 —— 把 A 放大 7 倍，看看会发生什么")
line("-")
A7 = A * 7
print(f"\n  A  的长度 = {np.linalg.norm(A):.6f}     A·B = {float(np.dot(A, B)):.8f}")
print(f"  7A 的长度 = {np.linalg.norm(A7):.6f}     7A·B = {float(np.dot(A7, B)):.8f}   ← 点积变了！")
print()
print(f"  但 cos 呢？")
print(f"      cos(A,  B) = {cos_formula(A, B):.10f}")
print(f"      cos(7A, B) = {cos_formula(A7, B):.10f}")
print("  >>> 一模一样。")
print()
print("  这说明：")
print("     · 点积 会被「向量长短」污染 —— 长向量点积天然更大，不公平")
print("     · 余弦 只看「方向」，不受长短影响 —— 这才是我们要的")
print("     · 模型在输出前就把向量缩成长度 1，于是点积 = 余弦，两边好处都拿到了")

# ------------------------------------------------------------
line("-")
print("疑问 2 之三：一个类比")
line("-")
print("""
  你要判断两个人「朝哪个方向看」，来判断他们看到的是不是同一片风景。

  如果只看「视线向量」，长一点短一点无所谓 —— 方向才是关键。
  短视线的点积小，长视线的点积大，但那不代表谁看得更准。

  归一化 = 要求所有人都站到「离原点 1 米」的圆上，
           这样「箭头末端落在圆上的哪个位置」就只反映方向，不掺长度。
           于是所有向量的点积和余弦变成同一个数，计算省一步，也不会有偏差。

  你的模型（text-embedding-v4）出厂就是归一化的：
      |v| = 1.0000000396 ≈ 1
""")

# ============================================================
line()
print("总结：三行代码，三个数，三个含义")
line()
sim = 1 - d[0]
print(f"""
  问句「{Q}」 vs 最相关片段

  distance   = {d[0]:.6f}   ← Chroma 给你的原始值，越小越像
  similarity = {sim:.6f}   ← 你自己翻的，越大越像，且数值等于 cos(夹角)
  夹角       = {np.degrees(np.arccos(np.clip(sim, -1, 1))):.2f}°

  转换公式：similarity = 1 - distance = 1 - (1 - cos) = cos
  那个 1 是「垂直」的坐标，不是余弦。
""")