"""
Agent 的工具箱。

这里是「模型能做的事」的清单。每个工具由三部分组成：
    1. 定义（给模型看的说明书）—— 见 TOOLS
    2. 实现（真正干活）        —— 见 _exec_xxx
    3. 路由（名字 → 实现）      —— 见 execute

设计原则：
    · 工具描述必须写清「什么时候用」，模型全靠这段话做判断
    · 工具返回的错误要能被模型读懂，它才知道下一步怎么改
    · 不要给模型太多工具，选择困难会让它乱调
"""
from __future__ import annotations

import logging

from rag import embeddings, store

logger = logging.getLogger(__name__)


# ==================================================================== 工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_kb",
            "description": (
                "在厨房知识库里做语义检索。知识库包含三类内容："
                "① 食材处理与烹饪要点（鸡蛋/番茄/青椒/肉类的挑选处理、食材保存、调味比例）；"
                "② 营养配比与饮食方案（三大营养素、常见食材营养、减脂/增肌方案、特殊人群）；"
                "③ 经典家常菜做法。"
                "凡是用户问具体做法、用量配比、营养知识、保存方法，都该先调用它。"
                "如果第一次结果不够，可以换个更具体的说法再查一次。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索词。要具体，用名词，比如「糖醋汁比例」「红烧肉焯水」「减脂期蛋白质」",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回几条，默认 4，最多 8",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dish",
            "description": (
                "按菜名精确查一道菜的完整做法和用料。"
                "知识库里目前只有 6 道菜：西红柿炒鸡蛋、宫保鸡丁、红烧肉、清蒸鲈鱼、手撕包菜、番茄牛腩。"
                "用户问这几道菜时优先用它，比 search_kb 更准（精确匹配菜名，不会召回无关片段）。"
                "不确定菜名时先用 list_dishes 看有哪些。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dish_name": {
                        "type": "string",
                        "description": "菜名，比如「红烧肉」。不用写序号",
                    },
                },
                "required": ["dish_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dishes",
            "description": "列出知识库里所有可用的菜名。当用户问「你会做什么」「有什么菜」时调用。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calc_nutrition",
            "description": (
                "按食材和用量计算热量、蛋白质、脂肪。"
                "凡是要给出具体数字（多少千卡、多少克蛋白质）的问题都必须调用，不要自己心算，"
                "大模型的算术不可靠。"
                "支持克和常见烹饪单位（勺/小勺/毫升），会自动换算。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "食材清单",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "食材名，如「鸡胸肉」"},
                                "grams": {"type": "number", "description": "克数，如 200"},
                                "amount": {"type": "number", "description": "用量（配合 unit 使用，如 2 勺）"},
                                "unit": {
                                    "type": "string",
                                    "description": "单位：g / ml / 勺 / 小勺。不填默认 g",
                                },
                            },
                            "required": ["name"],
                        },
                    }
                },
                "required": ["items"],
            },
        },
    },
]


# ==================================================================== 营养数据
# 每 100 克可食部分：(热量千卡, 蛋白质克, 脂肪克)
# kb=True 表示这个数字来自本项目知识库，False 表示来自通用食物成分表
NUTRITION: dict[str, tuple[float, float, float, bool]] = {
    # --- 知识库里有明确数值的（02-营养配比与饮食方案.md）---
    "鸡蛋": (140, 12.0, 10.0, True),
    "鸡胸肉": (165, 31.0, 3.6, True),
    "三文鱼": (208, 20.0, 13.0, True),
    "北豆腐": (116, 12.0, 7.2, True),
    "燕麦": (389, 17.0, 6.7, True),
    "西兰花": (34, 3.5, 0.4, True),
    # --- 以下来自通用食物成分表 ---
    "猪五花肉": (395, 13.6, 37.0, False),
    "猪里脊": (143, 20.3, 6.2, False),
    "猪排骨": (264, 18.3, 20.4, False),
    "牛腩": (332, 17.1, 29.3, False),
    "牛里脊": (107, 22.2, 0.9, False),
    "鸡腿肉": (181, 16.0, 13.0, False),
    "鸡翅": (194, 17.4, 11.8, False),
    "鲈鱼": (105, 18.6, 3.4, False),
    "草鱼": (113, 16.6, 5.2, False),
    "虾仁": (93, 18.6, 0.8, False),
    "五花肉片": (395, 13.6, 37.0, False),
    "米饭": (116, 2.6, 0.3, False),
    "面条": (110, 3.9, 0.4, False),
    "馒头": (223, 7.0, 1.1, False),
    "土豆": (77, 2.0, 0.2, False),
    "红薯": (86, 1.6, 0.2, False),
    "番茄": (20, 0.9, 0.2, False),
    "西红柿": (20, 0.9, 0.2, False),
    "青椒": (22, 1.0, 0.2, False),
    "尖椒": (22, 1.0, 0.2, False),
    "包菜": (24, 1.5, 0.2, False),
    "洋葱": (40, 1.1, 0.2, False),
    "胡萝卜": (39, 1.0, 0.2, False),
    "黄瓜": (16, 0.8, 0.2, False),
    "茄子": (23, 1.1, 0.2, False),
    "香菇": (26, 2.2, 0.3, False),
    "干辣椒": (298, 15.0, 12.0, False),
    "葱": (30, 1.7, 0.3, False),
    "姜": (41, 1.3, 0.6, False),
    "蒜": (126, 4.5, 0.2, False),
    # --- 调料 ---
    "食用油": (899, 0.0, 99.9, False),
    "白砂糖": (400, 0.0, 0.0, False),
    "冰糖": (397, 0.0, 0.0, False),
    "食盐": (0, 0.0, 0.0, False),
    "生抽": (63, 5.6, 0.1, False),
    "老抽": (63, 5.6, 0.1, False),
    "酱油": (63, 5.6, 0.1, False),
    "蚝油": (114, 3.0, 0.2, False),
    "醋": (31, 2.1, 0.3, False),
    "料酒": (65, 0.6, 0.0, False),
    "淀粉": (346, 1.2, 0.1, False),
    "番茄酱": (81, 4.9, 0.2, False),
    "豆瓣酱": (178, 13.6, 6.8, False),
    "炸花生米": (589, 21.7, 48.0, False),
    "花生米": (589, 21.7, 48.0, False),
    "浓肉汤": (30, 2.0, 2.0, False),
    "清水": (0, 0.0, 0.0, False),
}

# 别名 → 表里的标准名
ALIASES: dict[str, str] = {
    "五花肉": "猪五花肉",
    "带皮五花肉": "猪五花肉",
    "里脊": "猪里脊",
    "猪里脊肉": "猪里脊",
    "排骨": "猪排骨",
    "牛腩肉": "牛腩",
    "鸡腿": "鸡腿肉",
    "鱼": "鲈鱼",
    "虾": "虾仁",
    "米饭熟": "米饭",
    "杂粮饭": "米饭",
    "杂粮米饭": "米饭",
    "菜籽油": "食用油",
    "花生油": "食用油",
    "玉米油": "食用油",
    "油": "食用油",
    "糖": "白砂糖",
    "白糖": "白砂糖",
    "盐": "食盐",
    "味精": "食盐",
    "鸡精": "食盐",
    "马铃薯": "土豆",
    "西红柿": "番茄",
    "番茄中等": "番茄",
    "菜椒": "青椒",
    "甜椒": "青椒",
    "卷心菜": "包菜",
    "圆白菜": "包菜",
    "包心菜": "包菜",
    "小葱": "葱",
    "大葱": "葱",
    "生姜": "姜",
    "大蒜": "蒜",
    "蒜瓣": "蒜",
    "生粉": "淀粉",
    "水": "清水",
    "高汤": "浓肉汤",
    "骨汤": "浓肉汤",
    "鸡蛋液": "鸡蛋",
}

# 单位换算：1 单位 = ? 毫升
UNIT_ML = {
    "g": None, "克": None, "千克": None, "kg": None,
    "ml": 1.0, "毫升": 1.0,
    "勺": 15.0, "汤勺": 15.0, "大勺": 15.0, "tbsp": 15.0,
    "小勺": 5.0, "茶匙": 5.0, "tsp": 5.0,
}

# 每毫升多少克（粉状/酱状调料和水的密度不一样，不换算会差一倍）
DENSITY = {
    "白砂糖": 0.85, "冰糖": 0.85, "食盐": 1.2, "淀粉": 0.6,
    "生抽": 1.15, "老抽": 1.15, "酱油": 1.15, "蚝油": 1.3,
    "醋": 1.01, "料酒": 0.98, "番茄酱": 1.1, "豆瓣酱": 1.2,
    "食用油": 0.92, "清水": 1.0, "浓肉汤": 1.0,
}


# ==================================================================== 工具实现
def _normalize(name: str) -> str:
    return (name or "").strip().replace(" ", "").replace("　", "")


def _lookup(name: str) -> tuple[str, tuple[float, float, float, bool]] | None:
    """把用户写的食材名映射到营养表。先精确、再别名、最后包含匹配。"""
    key = _normalize(name)
    if not key:
        return None
    if key in NUTRITION:
        return key, NUTRITION[key]
    if key in ALIASES:
        std = ALIASES[key]
        return std, NUTRITION[std]

    # 包含匹配：取最长的那个，避免「油」匹配到「蚝油」
    best = None
    for std in NUTRITION:
        if std in key or key in std:
            if best is None or len(std) > len(best[0]):
                best = (std, NUTRITION[std])
    return best


def _to_grams(name: str, args: dict) -> tuple[float, str]:
    """把各种单位统一成克。返回 (克数, 换算说明)。"""
    if args.get("grams") is not None:
        g = float(args["grams"])
        return g, f"{g:g} 克"

    amount = args.get("amount")
    unit = str(args.get("unit") or "g").strip()
    if amount is None:
        return 0.0, "未给用量"
    amount = float(amount)

    if unit in ("g", "克"):
        return amount, f"{amount:g} 克"
    if unit in ("kg", "千克"):
        return amount * 1000, f"{amount:g} 千克"

    ml_per = UNIT_ML.get(unit)
    if ml_per is None:
        # 没见过的单位，按克处理，并明确告诉模型
        return amount, f"{amount:g} {unit}（按克计）"

    ml = amount * ml_per
    density = DENSITY.get(_lookup(name)[0] if _lookup(name) else name, 1.0)
    if ml_per == 1.0 and density == 1.0:
        return ml, f"{amount:g} {unit}"
    g = ml * density
    return g, f"{amount:g} {unit} ≈ {g:.0f} 克"


def _exec_search_kb(query: str, top_k: int = 4) -> dict:
    query = (query or "").strip()
    if not query:
        return {"ok": False, "error": "query 不能为空，请给出具体检索词"}

    k = max(1, min(int(top_k or 4), 8))
    vec = embeddings.embed_query(query)
    hits = store.search(vec, k=k)

    if not hits:
        return {
            "ok": True,
            "count": 0,
            "hits": [],
            "hint": "知识库里没有相关内容。可以换个说法再查一次，或者如实告诉用户知识库没有。",
        }

    return {
        "ok": True,
        "count": len(hits),
        "hits": [
            {
                "来源": h.get("filename", ""),
                "小节": h.get("label", ""),
                "相似度": round(float(h.get("similarity", 0)), 3),
                "内容": (h.get("text") or "")[:600],
            }
            for h in hits
        ],
    }


def _all_chunks() -> list[dict]:
    col = store._col()
    if col.count() == 0:
        return []
    data = col.get(include=["metadatas", "documents"])
    out = []
    for meta, doc in zip(data.get("metadatas") or [], data.get("documents") or []):
        out.append({
            "filename": (meta or {}).get("filename", ""),
            "label": (meta or {}).get("label", ""),
            "seq": (meta or {}).get("seq", 0),
            "text": doc or "",
        })
    return out


DISH_FILE = "03-"


def _dish_chunks() -> list[dict]:
    """只取菜谱文档里的片段。"""
    return [c for c in _all_chunks() if c["filename"].startswith(DISH_FILE)]


def _strip_ordinal(label: str) -> str:
    """「三、红烧肉」→「红烧肉」"""
    for p in ("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、"):
        if label.startswith(p):
            return label[len(p):].strip()
    return label.strip()


def _exec_get_dish(dish_name: str) -> dict:
    want = _normalize(dish_name)
    if not want:
        return {"ok": False, "error": "dish_name 不能为空"}

    dishes = _dish_chunks()
    if not dishes:
        return {"ok": False, "error": "知识库里没有菜谱"}

    # 精确 → 包含
    exact = [c for c in dishes if _strip_ordinal(c["label"]) == want]
    if not exact:
        exact = [c for c in dishes if want in c["label"] or _strip_ordinal(c["label"]) in want]

    if not exact:
        names = [_strip_ordinal(c["label"]) for c in dishes]
        return {
            "ok": False,
            "error": f"知识库里没有「{dish_name}」这道菜",
            "available": names,
            "hint": "请从 available 里选一个，或者用 search_kb 做语义检索。不要编造菜谱。",
        }

    c = exact[0]
    return {
        "ok": True,
        "dish": _strip_ordinal(c["label"]),
        "content": c["text"],
        "来源": c["filename"],
    }


def _exec_list_dishes() -> dict:
    dishes = _dish_chunks()
    return {
        "ok": True,
        "count": len(dishes),
        "dishes": [_strip_ordinal(c["label"]) for c in dishes],
        "note": "知识库只有这些菜。用户问别的菜时，如实说没有，可以给通用建议但要注明不是知识库内容。",
    }


def inventory() -> dict:
    """知识库里到底有什么。给「检索一条都没命中」的场景用。

    为什么需要：用户问了一个库里没有的东西，只回一句"没有"对他没用 ——
    他还得再猜一次该问什么。告诉他收录了哪几道菜、哪几份资料，
    他自己就能换个问法。

    这是查本地 Chroma，不走网络，所以随时调用都不花钱。
    """
    try:
        chunks = _all_chunks()
    except Exception as exc:          # 库没就绪之类，不能因为这个把对话搞崩
        logger.warning("读取知识库清单失败: %s", exc)
        return {"ok": False, "dishes": [], "files": [], "chunks": 0}

    dishes: list[str] = []
    files: list[str] = []
    for c in chunks:
        fn = c.get("filename", "")
        if fn and fn not in files:
            files.append(fn)
        if fn.startswith(DISH_FILE):
            label = _strip_ordinal(c.get("label", ""))
            if label and label not in dishes:
                dishes.append(label)

    return {"ok": True, "dishes": dishes, "files": files, "chunks": len(chunks)}


def _exec_calc_nutrition(items: list) -> dict:
    if not items:
        return {"ok": False, "error": "items 不能为空"}

    rows, unknown = [], []
    tot_k = tot_p = tot_f = 0.0

    for it in items:
        if not isinstance(it, dict):
            continue
        raw_name = it.get("name", "")
        hit = _lookup(raw_name)
        if hit is None:
            unknown.append(raw_name)
            continue

        std, (k100, p100, f100, from_kb) = hit
        grams, how = _to_grams(std, it)
        if grams <= 0:
            unknown.append(f"{raw_name}（用量为 0）")
            continue

        k = k100 * grams / 100
        p = p100 * grams / 100
        f = f100 * grams / 100
        tot_k += k
        tot_p += p
        tot_f += f
        rows.append({
            "食材": raw_name,
            "匹配到": std,
            "用量": how,
            "热量千卡": round(k, 1),
            "蛋白质克": round(p, 1),
            "脂肪克": round(f, 1),
            "数据来源": "知识库" if from_kb else "通用成分表",
        })

    if not rows:
        return {
            "ok": False,
            "error": "没有任何食材能识别",
            "unknown": unknown,
            "hint": "请换成更具体的食材名，比如「猪五花肉」而不是「肉」。",
        }

    # 三大营养素供能比
    e_p = tot_p * 4
    e_f = tot_f * 9
    e_c = max(tot_k - e_p - e_f, 0)
    total_e = e_p + e_f + e_c

    result = {
        "ok": True,
        "明细": rows,
        "合计": {
            "热量千卡": round(tot_k, 1),
            "蛋白质克": round(tot_p, 1),
            "脂肪克": round(tot_f, 1),
            "碳水克": round(e_c / 4, 1),
        },
    }
    if total_e > 0:
        result["供能比"] = {
            "蛋白质": f"{e_p / total_e * 100:.0f}%",
            "脂肪": f"{e_f / total_e * 100:.0f}%",
            "碳水": f"{e_c / total_e * 100:.0f}%",
        }
    if unknown:
        result["未识别"] = unknown
        result["hint"] = "未识别的食材没有计入合计。如果重要，换用通用名再算一次。"
    return result


# ==================================================================== 路由
_ROUTES = {
    "search_kb": _exec_search_kb,
    "get_dish": _exec_get_dish,
    "list_dishes": _exec_list_dishes,
    "calc_nutrition": _exec_calc_nutrition,
}


def execute(name: str, arguments: dict) -> dict:
    """执行一个工具调用。任何异常都转成模型能读懂的错误，不让整个流程崩掉。"""
    fn = _ROUTES.get(name)
    if fn is None:
        return {
            "ok": False,
            "error": f"没有名为「{name}」的工具",
            "available": list(_ROUTES),
        }
    try:
        return fn(**(arguments or {}))
    except TypeError as exc:
        return {"ok": False, "error": f"参数不对：{exc}"}
    except Exception as exc:
        logger.exception("工具 %s 执行失败", name)
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def names() -> list[str]:
    return list(_ROUTES)