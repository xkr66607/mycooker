"""
Agent 模式：让模型自己决定查不查、查几次、查什么。

和 rag/pipeline.py 的 stream_chat 的区别只有一句话：
    stream_chat      —— 代码固定检索一次，模型被动接收
    stream_agent     —— 模型通过工具调用自己发起检索，可以查多次

核心是一个循环：
    问模型 → 它要工具？→ 执行 → 把结果塞回去 → 再问 → ... → 它不要了 → 输出答案

三条纪律（都是踩过的坑）：
    1. 工具调用的流式碎片必须【按 index 分组】拼，组内拼、组间不拼
    2. 必须有步数上限，否则模型可能一路调下去烧光额度
    3. 工具返回的内容要截断，太长会撑爆上下文
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

import config
from memory import store as memory
from rag import pipeline, tools

logger = logging.getLogger(__name__)


# ==================================================================== 系统提示
AGENT_SYSTEM_PROMPT = """你是「小厨·私厨助手」，一个能查资料、能算数的厨房助手。

你可以调用工具。必须遵守下面 6 条：

1. 凡是涉及**具体做法、用量配比、食材处理、保存方法、营养知识**的问题，
   先调 search_kb 或 get_dish 查，不要凭记忆直接答。

2. 凡是需要给出**具体数字**（多少千卡、多少克蛋白质、多少脂肪）的问题，
   必须调 calc_nutrition 算，不要心算。大模型的算术不可靠。

3. 用户问的菜如果不在知识库里（知识库只有 6 道菜），先 get_dish 确认，
   确认没有就如实说「知识库里没有这道菜」。可以给通用建议，
   但必须明确标注「以下是通用经验，不是知识库内容」。

4. **引用必须真实**：只能引用工具真正返回过的内容，格式用 [编号]。
   工具没给的内容不要加引用编号，也不要编造编号。

5. 工具结果不够时，可以换个更具体的关键词再查一次。同一个问题最多查 3 次。
   查了 3 次还是没有，就如实说明知识库里没有，不要硬编。

6. 最后用中文 Markdown 回答，结构清晰。不要把工具调用的内部细节
   （JSON、参数、函数名）写进答案里，用户不需要看这些。"""


# 闲聊路线用的提示词：没有工具，也就不用讲工具规则。
# 如果闲聊也套上面那段"必须调工具查"的提示词，模型会因为没有工具可用而无所适从，
# 或者干脆编造一个查询过程出来。
CHAT_SYSTEM_PROMPT = """你是「小厨·私厨助手」，一个懂做饭、懂营养的助手。

用户在跟你闲聊，或者说了句客气话。自然地回应就好，不用查资料，也不用讲长度。

如果对方顺口问到了具体的菜或营养问题，简单回应一句，然后邀请他把问题说清楚
（比如「想做什么菜」「想算哪种食材」），这样你才能帮上忙。

语气轻松、别端着，不要用"作为 AI 助手"这种说法。"""


# 用户问的菜名里可能带这些后缀
_DISH_NOISE = ("怎么做", "的做法", "怎么烧", "怎么炒", "菜谱", "做法", "做法呢", "？", "?")


def _static_summary(name: str, result: dict) -> str:
    """把工具结果压缩成一句人话，给前端显示进度用。"""
    if not result.get("ok"):
        return result.get("error", "没查到")[:40]

    if name == "search_kb":
        n = result.get("count", 0)
        if n == 0:
            return "没找到相关资料"
        top = (result.get("hits") or [{}])[0]
        return f"查到 {n} 条，最相关：{top.get('小节', '')}"

    if name == "get_dish":
        return f"拿到「{result.get('dish', '')}」的完整做法"

    if name == "list_dishes":
        return f"知识库共 {result.get('count', 0)} 道菜"

    if name == "calc_nutrition":
        t = result.get("合计") or {}
        return f"算出 {t.get('热量千卡', 0)} 千卡，蛋白质 {t.get('蛋白质克', 0)} 克"

    return "完成"


class _SourceBook:
    """给工具返回的资料统一编号，保证模型引用的 [n] 和前端显示的是同一批。

    为什么必须有它：如果不统一编号，模型会自己发明 [1][2]，
    前端拿到的 sources 数组跟它的编号对不上，引用就全错了。
    """

    def __init__(self) -> None:
        self.items: list[dict] = []
        self._seen: set[str] = set()

    def _key(self, filename: str, label: str, text: str) -> str:
        return f"{filename}|{label}|{text[:60]}"

    def add(self, filename: str, label: str, text: str, similarity: float | None) -> int:
        key = self._key(filename, label, text)
        if key in self._seen:
            # 已经收过，复用它原来的编号
            for it in self.items:
                if it["_key"] == key:
                    return it["n"]
        n = len(self.items) + 1
        self._seen.add(key)
        self.items.append({
            "_key": key,
            "n": n,
            "filename": filename,
            "label": label,
            "text": text,
            "similarity": similarity,
        })
        return n

    def public(self) -> list[dict]:
        """给前端看的。字段必须和 renderSources 对齐：
        index / filename / label / similarity / preview

        ⚠️ similarity 必须是数字。前端会调 .toFixed(2)，
        给 None 会直接抛异常，整条消息渲染不出来。
        精确匹配拿到的菜谱没有相似度概念，按 1.0（完全相关）处理。
        """
        out = []
        for it in self.items:
            sim = it["similarity"]
            out.append({
                "index": it["n"],
                "filename": it["filename"],
                "label": it["label"],
                "similarity": float(sim) if sim is not None else 1.0,
                "preview": (it["text"] or "")[:160].replace("\n", " "),
            })
        return out

    def __len__(self) -> int:
        return len(self.items)


def _annotate(name: str, result: dict, book: _SourceBook) -> dict:
    """给工具返回的资料打上编号，模型才能正确引用。"""
    if not result.get("ok"):
        return result

    if name == "search_kb":
        for h in result.get("hits") or []:
            n = book.add(
                h.get("来源", ""), h.get("小节", ""), h.get("内容", ""),
                h.get("相似度"),
            )
            h["编号"] = n

    elif name == "get_dish":
        n = book.add(
            result.get("来源", ""), result.get("dish", ""), result.get("content", ""),
            None,
        )
        result["编号"] = n

    return result


def _trim(result: dict, limit: int) -> dict:
    """工具结果太长会撑爆上下文，也会让模型抓不住重点。"""
    raw = json.dumps(result, ensure_ascii=False)
    if len(raw) <= limit:
        return result
    return {
        "ok": True,
        "truncated": True,
        "note": f"原始结果 {len(raw)} 字，已截断到 {limit} 字。需要更多细节请缩小查询范围。",
        "preview": raw[:limit],
    }


def _assemble(tool_buf: dict[int, dict]) -> list[dict]:
    """把流式碎片拼成完整的工具调用。

    ⚠️ 关键：必须按 index 分组。
    模型可能并行发多个调用（实测过同时发 2 个 search_kb），
    把所有碎片直接 join 会得到 'search_kbsearch_kb' 和 '{...}{...}'，
    json.loads 会报 Extra data。
    """
    calls = []
    for idx in sorted(tool_buf):
        buf = tool_buf[idx]
        args_raw = buf.get("arguments") or "{}"
        try:
            args = json.loads(args_raw) if args_raw.strip() else {}
        except json.JSONDecodeError:
            args = {}
        calls.append({
            "id": buf.get("id") or f"call_{idx}",
            "name": buf.get("name") or "",
            "arguments_raw": args_raw,
            "arguments": args,
        })
    return calls


async def stream_agent(
    question: str,
    conversation_id: str | None = None,
    image_url: str | None = None,
    history: list[dict] | None = None,
    tools_enabled: bool = True,
):
    """Agent 模式的流式回答。事件类型与 stream_chat 兼容，额外多了工具相关事件。

    tools_enabled=False 时退化成「一次模型调用 + 流式输出」，
    用在闲聊路线上 —— 不传工具、不检索，最省。
    这样两条路线共用同一套事件协议和落库逻辑，不用写两份。
    """
    question = (question or "").strip()
    if not question:
        yield {"type": "error", "message": "问题不能为空"}
        return

    system_prompt = AGENT_SYSTEM_PROMPT if tools_enabled else CHAT_SYSTEM_PROMPT
    max_steps = config.AGENT_MAX_STEPS if tools_enabled else 1

    # 1) 会话与历史
    try:
        cid = memory.ensure_conversation(conversation_id, question[:40])
        yield {"type": "conversation", "id": cid}
        conversation_id = cid
    except Exception as exc:
        logger.exception("建会话失败")
        yield {"type": "error", "message": f"建会话失败: {exc}"}
        return

    if history is None:
        try:
            history = memory.get_history(conversation_id)
        except Exception:
            history = []
    history = [
        {"role": h.get("role"), "content": h.get("content")}
        for h in history
        if h.get("content") and h.get("role") in ("user", "assistant")
    ]

    # 2) 图片识别（有图先认图，把识别结果并进用户输入）
    extra = ""
    if image_url:
        try:
            ingredients = await pipeline.recognize_ingredients(image_url)
            if ingredients:
                yield {"type": "ingredients", "text": ingredients}
                extra = f"\n\n[用户上传了冰箱食材照片，识别到：{ingredients}]"
        except Exception as exc:
            logger.warning("图片识别失败: %s", exc)

    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": question + extra})

    book = _SourceBook()
    stats = {"steps": 0, "tool_calls": 0, "tools": [], "tokens": 0}
    started = time.time()
    answer_parts: list[str] = []
    final_finish: str | None = None
    think_chars = 0

    client = pipeline._get_client()

    # 3) 主循环
    force_final = False
    for step in range(max_steps + 1):
        is_last_chance = step >= max_steps
        stats["steps"] = step + 1

        # 每轮开始先把已收集的资料推给前端（可以重复推，前端是覆盖渲染）
        if book:
            yield {"type": "sources", "sources": book.public()}

        round_content: list[str] = []
        tool_buf: dict[int, dict] = {}
        finish_reason = None

        try:
            stream = await client.chat.completions.create(
                model=config.CHAT_MODEL,
                messages=messages,
                tools=tools.TOOLS if (tools_enabled and not force_final) else None,
                tool_choice="auto" if (tools_enabled and not force_final) else None,
                stream=True,
                max_tokens=config.AGENT_MAX_TOKENS,
            )
        except Exception as exc:
            logger.exception("Agent 第 %s 轮调用失败", step + 1)
            yield {"type": "error", "message": pipeline._explain_error(exc)}
            return

        try:
            async for chunk in stream:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                finish_reason = choice.finish_reason or finish_reason
                delta = choice.delta

                think = getattr(delta, "reasoning_content", None)
                if think:
                    think_chars += len(think)
                    yield {"type": "thinking", "text": think}

                piece = getattr(delta, "content", None)
                if piece:
                    round_content.append(piece)
                    answer_parts.append(piece)
                    yield {"type": "delta", "text": piece}

                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = tc.index if tc.index is not None else 0
                    buf = tool_buf.setdefault(idx, {"id": None, "name": "", "arguments": ""})
                    if getattr(tc, "id", None):
                        buf["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            buf["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            buf["arguments"] += fn.arguments
        except Exception as exc:
            logger.exception("Agent 流读取中断")
            yield {"type": "error", "message": f"读取模型输出时出错: {exc}"}
            return

        # 本轮没有工具调用 → 这就是最终答案
        if not tool_buf:
            final_finish = finish_reason
            break

        # ---- 本轮是工具调用 ----
        # 如果模型在调用工具的同时还吐了正文（很少见），前面已经推给前端了，
        # 那部分是"半句话"，得让前端清掉，否则会混进最终答案。
        if round_content:
            answer_parts.clear()
            yield {"type": "answer_reset"}

        calls = _assemble(tool_buf)
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": c["id"], "type": "function",
                 "function": {"name": c["name"], "arguments": c["arguments_raw"]}}
                for c in calls
            ],
        })

        for c in calls:
            stats["tool_calls"] += 1
            stats["tools"].append(c["name"])
            yield {
                "type": "tool_start",
                "name": c["name"],
                "args": c["arguments"],
                "n": stats["tool_calls"],
            }

            result = await asyncio.to_thread(tools.execute, c["name"], c["arguments"])
            result = _annotate(c["name"], result, book)
            result = _trim(result, config.AGENT_MAX_TOOL_CHARS)

            summary = _static_summary(c["name"], result)
            yield {
                "type": "tool_done",
                "name": c["name"],
                "summary": summary,
                "ok": bool(result.get("ok")),
                "n": stats["tool_calls"],
            }

            messages.append({
                "role": "tool",
                "tool_call_id": c["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })

        # 步数用完了，下一轮禁用工具，逼它基于已有资料收尾
        if step + 1 >= max_steps:
            force_final = True
            logger.warning("达到步数上限 %s，强制收尾", max_steps)

    answer = "".join(answer_parts).strip()

    if book:
        yield {"type": "sources", "sources": book.public()}

    if not answer:
        yield {"type": "error", "message": pipeline._explain_empty(final_finish, think_chars)}
        return

    # 4) 落库
    cited = pipeline._extract_citations(answer, book.public())
    try:
        memory.add_message(conversation_id, "user", question, [])
        memory.add_message(conversation_id, "assistant", answer, cited)
    except Exception:
        logger.exception("保存消息失败（不影响本次回答）")

    elapsed = round(time.time() - started, 1)
    logger.info(
        "Agent 完成 | 步数=%s 工具=%s 耗时=%ss 答案=%s字",
        stats["steps"], stats["tools"], elapsed, len(answer),
    )

    yield {
        "type": "done",
        "citations": cited,
        "agent": {
            "steps": stats["steps"],
            "tool_calls": stats["tool_calls"],
            "tools": stats["tools"],
            "sources": len(book),
            "elapsed_s": elapsed,
        },
    }