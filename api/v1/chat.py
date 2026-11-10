"""
对话接口。

SSE（Server-Sent Events）为什么适合这里：
普通 HTTP 要等模型全部生成完才返回，用户盯着白屏十几秒；
SSE 是一边生成一边推，用户看到字一个个冒出来。
协议很简单：响应体是一行行 "data: {json}\\n\\n"，前端用 EventSource
或 fetch+ReadableStream 解析即可。
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from memory import store as memory
from rag import pipeline

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    conversation_id: str | None = None
    image_url: str | None = None


def _sse(event: dict) -> str:
    """一条 SSE 事件。ensure_ascii=False 保证中文不变成 \\uXXXX。"""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话：返回 SSE 事件流。"""

    async def gen():
        try:
            async for event in pipeline.stream_chat(
                question=req.message.strip(),
                conversation_id=req.conversation_id,
                image_url=req.image_url,
            ):
                yield _sse(event)
        except Exception as exc:  # 兜底：任何未捕获异常都转成一条 error 事件
            logger.exception("对话流异常")
            yield _sse({"type": "error", "message": str(exc)})
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",   # 关掉 nginx 缓冲，否则流式会被攒起来
        },
    )


@router.get("/chat/conversations")
async def conversations():
    return {"success": True, "data": memory.list_conversations()}


@router.get("/chat/messages")
async def messages(conversation_id: str):
    return {"success": True, "data": memory.get_messages(conversation_id)}


@router.delete("/chat/conversations/{conversation_id}")
async def remove_conversation(conversation_id: str):
    n = memory.delete_conversation(conversation_id)
    if not n:
        raise HTTPException(404, "会话不存在")
    return {"success": True, "deleted": n}