"""
知识库管理接口。

上传走 multipart/form-data；入库是阻塞操作（解析+向量化可能要几十秒），
所以丢进线程池，避免卡住整个服务。
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

import config
from rag import embeddings, ingest, store

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/kb/upload")
async def upload(file: UploadFile = File(...)):
    """上传一个文档并入库。"""
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "文件为空")

    try:
        meta = await asyncio.to_thread(ingest.ingest, file.filename or "unnamed", raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("入库失败")
        raise HTTPException(500, f"入库失败: {exc}") from exc

    return {"success": True, "data": meta}


@router.get("/kb/sources")
async def sources():
    return {"success": True, "data": await asyncio.to_thread(store.list_sources)}


@router.delete("/kb/sources/{source_id}")
async def remove_source(source_id: str):
    n = await asyncio.to_thread(store.delete_source, source_id)
    if not n:
        raise HTTPException(404, "该文档不存在")
    return {"success": True, "deleted": n}


@router.get("/kb/stats")
async def stats():
    return {"success": True, "data": await asyncio.to_thread(store.stats)}


class SearchRequest(BaseModel):
    query: str
    k: int = 5


@router.post("/kb/search")
async def search(req: SearchRequest):
    """检索测试：不经过模型，直接看命中什么片段。调试 RAG 的第一工具。"""
    if not req.query.strip():
        raise HTTPException(400, "查询不能为空")
    try:
        vec = await asyncio.to_thread(embeddings.embed_query, req.query)
        hits = await asyncio.to_thread(store.search, vec, req.k)
    except Exception as exc:
        raise HTTPException(500, f"检索失败: {exc}") from exc
    return {"success": True, "data": hits}


@router.get("/kb/config")
async def kb_config():
    """把当前生效的切分/检索参数暴露给前端，方便用户知道系统怎么配的。"""
    return {
        "success": True,
        "data": {
            "chunk_size": config.CHUNK_SIZE,
            "chunk_overlap": config.CHUNK_OVERLAP,
            "top_k": config.TOP_K,
            "min_score": config.MIN_SCORE,
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dim": config.EMBEDDING_DIM,
            "chat_model": config.CHAT_MODEL,
            "vision_model": config.VISION_MODEL,
            "allowed_suffix": sorted(config.ALLOWED_SUFFIX),
            "max_file_mb": config.MAX_FILE_MB,
        },
    }