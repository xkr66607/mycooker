"""路由器的单元测试：把已知该走哪条路的问题全过一遍。

这些用例不是编的，每一条都对应一次实测会翻车的场景。
加规则前先跑一遍，加完再跑一遍 —— 不然改 A 会把 B 弄坏。
"""
import sys

sys.path.insert(0, r"D:\Ai\Langchain\mycooker")

from rag import router

# (问题, 期望路线, 为什么)
CASES = [
    # ---- 闲聊：不该检索 ----
    ("你好呀，今天心情不错", "chat", "寒暄"),
    ("谢谢！", "chat", "感谢"),
    ("好的，明白了", "chat", "确认"),

    # ---- 单跳：检索一次就够 ----
    ("糖醋汁的番茄酱和糖是什么比例？", "rag", "单一事实"),
    ("鸡蛋怎么保存比较久？", "rag", "单一事实"),
    ("减脂期蛋白质每天要吃多少？", "rag", "查知识库现成数字，不需要算"),
    ("五花肉焯水用冷水还是热水？", "rag", "单一事实"),
    ("西兰花多少卡？", "rag", "单食材热量，能直接查到"),

    # ---- 复杂：必须 Agent ----
    ("我想做红烧肉，按知识库的用量算，这一锅多少热量？一人份又是多少？",
     "agent", "计算 + 两个问题"),
    ("知识库里有哪几道菜？红烧肉的用料列一下", "agent", "列举，语义检索会漏"),
    ("糖醋排骨怎么做？", "agent", "做法请求，要交叉引用"),
    ("两个人吃，需要多少克五花肉？", "agent", "要按人数折算"),
    ("我想减脂，一天吃多少热量合适？还有蛋白质怎么配？", "agent", "多诉求"),
    ("帮我算 200 克鸡胸肉多少蛋白质", "agent", "计算"),
    ("西红柿炒鸡蛋和宫保鸡丁哪个热量高？", "agent", "两个问题，要比较"),

    # ---- 边界：不能误判成闲聊 ----
    ("你好，我想学做菜", "rag", "开头是寒暄但其实是请求"),
    ("谢谢，那红烧肉怎么做？", "agent", "寒暄开头但是做法请求"),
]


def main():
    print("=" * 96)
    print(f"{'判定':<7}{'期望':<7}{'':<3}{'理由':<26}{'问题'}")
    print("=" * 96)

    bad = []
    for q, want, note in CASES:
        got, why = router.route(q)
        ok = got == want
        if not ok:
            bad.append((q, want, got, why))
        print(f"{got:<7}{want:<7}{'✔' if ok else '✘':<3}{note:<26}{q[:40]}")
        if not ok:
            print(f"{'':<44}→ 实际理由: {why}")

    print("=" * 96)
    print(f"  {len(CASES) - len(bad)}/{len(CASES)} 通过")
    print()

    if bad:
        print("  判错的：")
        for q, want, got, why in bad:
            print(f"    {q[:46]}")
            print(f"      期望 {want}，实际 {got}（{why}）")
        print()
        return 1

    print("=" * 96)
    print("  每条路各分到几题：")
    for m in ("chat", "rag", "agent"):
        n = sum(1 for q, w, _ in CASES if w == m)
        print(f"    {m:<6} {n} 题")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())