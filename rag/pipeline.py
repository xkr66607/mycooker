"""
RAG 主流程：检索 → 组装上下文 → 让模型基于上下文生成。

关键取舍（面试会被问，先写清楚）：
1. 检索不到就明说"没找到"，不允许模型拿常识硬编 —— 这是幻觉的主要来源
2. 引用用 [1][2] 标注，和返回给前端的 sources 数组下标一一对应
3. 上下文长度设上限，超出就截断，避免超出模型窗口
4. 阻塞调用（embedding/检索）丢到线程池，不卡事件循环
"""
from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

from openai import AsyncOpenAI

import config
from memory import store as memory
from rag import embeddings, store

logger = logging.getLogger(__name__)

# 对话和视觉可能是两家不同的服务商，各用一个客户端
_chat_client: AsyncOpenAI | None = None
_vision_client: AsyncOpenAI | None = None

SYSTEM_PROMPT = """你是「小厨」，一位专业的私人厨房 AI 助手。

【服务范围】饮食搭配、营养成分、食材选购与处理、菜谱做法、烹饪技巧、食材保存、特殊饮食（减脂/增肌/控糖等）。

【回答规则】
1. **优先使用【知识库检索结果】**中提供的信息回答。用到了哪一段，就在那句话末尾标注对应编号，如 [1]、[2]。
2. **引用必须真实**：只有当某条检索结果确实支撑了这句话时才能标注。如果检索结果和问题无关，**不要为了凑引用而强行标注**，直接说明知识库中没有相关内容。
3. 如果检索结果不足以回答问题，要**明确说明**"知识库里暂时没有这方面的资料"，然后才可以给出通用建议，并注明"（以下为通用经验，非知识库内容）"。
4. **绝不编造**知识库里没有的菜谱用量、营养成分数值或来源。
5. 回答用中文，条理清晰，能上手操作；给出用量时写清分量。
6. 如果用户提供了食材照片，先确认识别到的食材，再给建议。
7. 不要输出与厨房饮食无关的内容。"""


def _get_client() -> AsyncOpenAI:
    """对话客户端。CHAT_* 可以指向千问、DeepSeek 或任意 OpenAI 兼容服务。"""
    global _chat_client
    if _chat_client is None:
        missing = config.assert_ready()
        if missing:
            raise RuntimeError(f"缺少配置: {', '.join(missing)}，请在 .env 中填写")
        _chat_client = AsyncOpenAI(
            api_key=config.CHAT_API_KEY,
            base_url=config.CHAT_BASE_URL,
            timeout=120,
        )
    return _chat_client


def _get_vision_client() -> AsyncOpenAI:
    """视觉客户端。单独一个，因为对话换成 DeepSeek 后它没有多模态能力，
    图片识别必须继续走千问，两者不能共用一个 base_url。"""
    global _vision_client
    if _vision_client is None:
        if not config.VISION_API_KEY:
            raise RuntimeError("缺少 VISION_API_KEY（或 DASHSCOPE_API_KEY），无法识别图片")
        _vision_client = AsyncOpenAI(
            api_key=config.VISION_API_KEY,
            base_url=config.VISION_BASE_URL,
            timeout=120,
        )
    return _vision_client


# ------------------------------------------------------------------ 视觉识别食材
async def recognize_ingredients(image_url: str) -> str:
    """用视觉模型从照片里认出食材清单。失败返回空串，不阻断主流程。"""
    try:
        client = _get_vision_client()
        resp = await client.chat.completions.create(
            model=config.VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "识别这张图片里所有的食材（蔬菜/肉类/蛋类/主食/调料）。"
                                    "只返回食材名称，用中文顿号分隔，不要任何解释。"
                                    "例如：鸡蛋、西红柿、青椒",
                        },
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            # ⚠️ 这里不能给小。推理模型（deepseek-v4.1-flash）先花 token 思考，
            #    再花 token 回答。给 200 的话思考就烧光了，content 返回空串，
            #    表现是「图片识别静默失效」——这个坑踩过一次。
            max_tokens=config.VISION_MAX_TOKENS,
        )
        msg = resp.choices[0].message
        text = (msg.content or "").strip()
        if not text:
            # 常见原因：思考吃光配额。把现场信息记下来，别静默失败。
            think = getattr(msg, "reasoning_content", None) or ""
            logger.warning(
                "视觉模型返回空正文（model=%s，思考内容 %s 字，finish_reason=%s）。"
                "如果思考内容不为空，说明 max_tokens=%s 太小，调大 VISION_MAX_TOKENS。",
                config.VISION_MODEL, len(think),
                resp.choices[0].finish_reason, config.VISION_MAX_TOKENS,
            )
        logger.info("视觉识别结果: %s", text)
        return text
    except Exception as exc:
        logger.warning("视觉识别失败，忽略图片: %s", exc)
        return ""


def _build_query(question: str, history: list[dict]) -> str:
    """
    检索用的查询 ≠ 用户的原始问句。

    多轮对话里经常出现「那减脂版怎么调整？」这种问题，
    单独拿去检索几乎什么都搜不到，因为它没有具体名词。
    把上一轮的用户提问拼进来，指代就能被自动补全，
    这是零成本、不额外调用的"查询改写"。

    只在问题偏短、且明显是承接上文时才拼接，避免把无关历史带进来。
    """
    q = question.strip()
    if not history or len(q) > 30:
        return q

    # 找最近一条用户消息
    last_user = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").strip()
            break

    # 已经很具体的问题不再拼接
    if not last_user or len(last_user) < 4:
        return q

    return f"{last_user} {q}"


# ------------------------------------------------------------------ 检索
async def retrieve(query: str) -> list[dict]:
    """把问题向量化后在库里检索。任何异常都降级为空列表。"""
    if not query.strip():
        return []
    try:
        vec = await asyncio.to_thread(embeddings.embed_query, query)
        hits = await asyncio.to_thread(store.search, vec)
        logger.info("检索「%s」命中 %s 条", query[:40], len(hits))
        return hits
    except Exception as exc:
        logger.warning("检索失败，降级为无知识库回答: %s", exc)
        return []


def build_context(hits: list[dict]) -> str:
    """把检索片段渲染成带编号的上下文块，总长度受 MAX_CONTEXT_CHARS 限制。"""
    if not hits:
        return ""

    blocks: list[str] = []
    used = 0
    for i, hit in enumerate(hits, start=1):
        head = f"[{i}] 《{hit['filename']}》{(' · ' + hit['label']) if hit['label'] else ''}（相关度 {hit['similarity']:.2f}）"
        body = hit["text"].strip()
        block = f"{head}\n{body}"
        if used + len(block) > config.MAX_CONTEXT_CHARS:
            # 至少保留第一条，剩下的截断
            if blocks:
                break
            block = block[: config.MAX_CONTEXT_CHARS]
        blocks.append(block)
        used += len(block) + 2

    return "\n\n".join(blocks)


def _messages(question: str, history: list[dict], facts: str, context: str) -> list[dict]:
    """组装最终送进模型的 messages。顺序很重要：系统 → 事实 → 上下文 → 历史 → 当前问题。"""
    system = SYSTEM_PROMPT

    if facts:
        system += f"\n\n【已知用户的长期偏好】\n{facts}"

    if context:
        system += (
            "\n\n【知识库检索结果】\n"
            f"{context}\n\n"
            "以上是本轮检索到的资料，请优先据此回答，并用 [编号] 标注引用。"
        )
    else:
        system += (
            "\n\n【知识库检索结果】\n（本轮未检索到相关资料）\n"
            "请明确告知用户知识库中没有找到，再给出通用建议并注明来源性质。"
        )

    msgs: list[dict] = [{"role": "system", "content": system}]
    for m in history:
        if m["role"] in ("user", "assistant"):
            msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": question})
    return msgs


# ------------------------------------------------------------------ 主入口
async def stream_chat(
    question: str,
    conversation_id: str | None,
    image_url: str | None = None,
) -> AsyncGenerator[dict, None]:
    """
    产出事件流（由 API 层转成 SSE）：
      {"type": "conversation", "id": ...}
      {"type": "ingredients", "text": ...}
      {"type": "sources", "sources": [...]}
      {"type": "delta", "text": "..."}
      {"type": "done", "citations": [...]}
      {"type": "error", "message": "..."}
    """
    # 1) 会话
    cid = memory.ensure_conversation(conversation_id, question)
    yield {"type": "conversation", "id": cid}

    # 2) 图片 → 食材（可选）
    ingredients = ""
    if image_url:
        ingredients = await recognize_ingredients(image_url)
        if ingredients:
            yield {"type": "ingredients", "text": ingredients}

    # 3) 取历史（检索前就要，查询改写依赖它）
    history = memory.get_history(cid)

    # 4) 检索：短问句会拼接上一轮提问，补全指代
    query = _build_query(question, history)
    if ingredients:
        query = f"{query} {ingredients}".strip()
    hits = await retrieve(query)

    # 只把真正会展示的字段发给前端
    sources = [
        {
            "index": i,
            "filename": h["filename"],
            "label": h["label"],
            "similarity": h["similarity"],
            "preview": h["text"][:160].replace("\n", " "),
        }
        for i, h in enumerate(hits, start=1)
    ]
    yield {"type": "sources", "sources": sources}

    # 5) 组装并生成
    facts = memory.facts_as_prompt()
    context = build_context(hits)
    messages = _messages(question, history, facts, context)

    answer_parts: list[str] = []
    try:
        client = _get_client()
        stream = await client.chat.completions.create(
            model=config.CHAT_MODEL,
            messages=messages,
            stream=True,
            temperature=0.6,
            max_tokens=config.CHAT_MAX_TOKENS,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            # 推理模型（deepseek-v4.1-flash 等）会先吐一大段思考过程，
            # 放在 reasoning_content 里。这段不能混进正文，否则答案里全是内心戏；
            # 但完全丢掉的话，用户会盯着空白屏幕等好几秒。
            # 所以单独发一个 thinking 事件，前端只用来显示"思考中"。
            think = getattr(delta, "reasoning_content", None)
            if think:
                yield {"type": "thinking", "text": think}

            piece = getattr(delta, "content", None)
            if piece:
                if not answer_parts:
                    yield {"type": "answer_start"}
                answer_parts.append(piece)
                yield {"type": "delta", "text": piece}
    except Exception as exc:
        logger.exception("生成失败")
        yield {"type": "error", "message": _explain_error(exc)}
        return

    answer = "".join(answer_parts).strip()

    # 5) 落库
    cited = _extract_citations(answer, sources)
    memory.add_message(cid, "user", question, [])
    memory.add_message(cid, "assistant", answer, cited)

    yield {"type": "done", "citations": cited}


def _explain_error(exc: Exception) -> str:
    """把底层异常翻译成人能看懂的话。

    最常见的坑：CHAT_MODEL 填了别家的模型名。
    DeepSeek 官方 API 叫 deepseek-chat / deepseek-reasoner，
    但通过千问（DashScope）调用时得叫 deepseek-v4.1-flash / deepseek-v4-pro。
    名字不对会得到 404「The model xxx does not exist」，而原始报错很难懂。
    """
    text = str(exc)
    low = text.lower()

    if "does not exist" in low or "model_not_found" in low or "model not exist" in low:
        return (
            f"模型名不对：{config.CHAT_MODEL}\n"
            "  这个模型在当前服务商那里不存在。检查 .env 里的 CHAT_MODEL：\n"
            "    · 通过千问(DashScope)调用 → deepseek-v4.1-flash / deepseek-v4-pro / qwen-plus\n"
            "    · 通过 DeepSeek 官方 API → 需同时设 CHAT_BASE_URL=https://api.deepseek.com，"
            "模型名才是 deepseek-chat\n"
            "  两家平台的模型命名不一样，这是最容易踩的坑。"
        )
    if "401" in low or "invalid_api_key" in low or "authentication" in low:
        return (
            f"鉴权失败：{config.CHAT_API_KEY[:6]}...（{len(config.CHAT_API_KEY)} 字符）\n"
            "  检查 .env 里的 CHAT_API_KEY / DASHSCOPE_API_KEY 是否正确、是否过期。"
        )
    if "429" in low or "rate limit" in low:
        return "调用太频繁被限流了，等几秒再试。"
    if "insufficient" in low or "balance" in low or "quota" in low:
        return "账户余额或额度不足，去控制台充值。"
    return f"生成失败: {text}"


def _extract_citations(answer: str, sources: list[dict]) -> list[dict]:
    """
    从回答正文里解析 [1] [2] 这类标记，返回真正被引用的来源。
    注意：模型可能编出越界编号，所以必须按 sources 长度做边界校验。
    """
    import re

    used: list[dict] = []
    seen: set[int] = set()
    for m in re.finditer(r"\[(\d{1,2})\]", answer):
        idx = int(m.group(1))
        if idx in seen or not (1 <= idx <= len(sources)):
            continue
        seen.add(idx)
        used.append(sources[idx - 1])
    return used