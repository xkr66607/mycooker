"""
向量库封装（Chroma 持久化）。

为什么不直接用 Chroma 的自动 embedding：
自己算向量才能控制"文档用 document 类型、查询用 query 类型"，
并且 batch / 重试 / 顺序还原都由我们掌握，行为更可预测。

距离 → 相似度：
collection 用 cosine 空间，Chroma 返回的是"余弦距离"，
相似度 = 1 - 距离。上层一律用 similarity（越大越相关）。
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

import chromadb

import config
from rag.splitter import Chunk

logger = logging.getLogger(__name__)

_client = None
_collection = None


def _col():
    """惰性初始化，避免 import 时就落盘。"""
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=str(config.CHROMA_DIR))
        _collection = _client.get_or_create_collection(
            name=config.COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("向量库就绪: %s (%s 条)", config.CHROMA_DIR, _collection.count())
    return _collection


# ------------------------------------------------------------------ 写入
def add_document(filename: str, chunks: list[Chunk], vectors: list[list[float]]) -> dict:
    """一个文件的所有切片一次性入库，返回该文档的元信息。"""
    if len(chunks) != len(vectors):
        raise ValueError(f"切片数({len(chunks)})与向量数({len(vectors)})不一致")

    source_id = uuid.uuid4().hex[:12]
    uploaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    ids = [f"{source_id}:{c.index}" for c in chunks]
    metadatas = [
        {
            "source_id": source_id,
            "filename": filename,
            "label": c.label,
            "seq": c.index,
            "uploaded_at": uploaded_at,
        }
        for c in chunks
    ]

    _col().add(
        ids=ids,
        embeddings=vectors,
        documents=[c.text for c in chunks],
        metadatas=metadatas,
    )

    logger.info("已入库 %s: %s 个片段 (source_id=%s)", filename, len(chunks), source_id)
    return {
        "source_id": source_id,
        "filename": filename,
        "chunks": len(chunks),
        "uploaded_at": uploaded_at,
    }


# ------------------------------------------------------------------ 检索
def search(query_vec: list[float], k: int | None = None, source_id: str | None = None) -> list[dict]:
    """向量相似度检索，返回按相似度降序的片段。"""
    col = _col()
    if col.count() == 0:
        return []

    k = k or config.TOP_K
    where = {"source_id": source_id} if source_id else None

    res = col.query(
        query_embeddings=[query_vec],
        n_results=min(k, col.count()),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    out: list[dict] = []
    for text, meta, dist in zip(docs, metas, dists):
        similarity = 1.0 - float(dist)          # cosine 距离 → 相似度
        if similarity < config.MIN_SCORE:        # 太不相关的直接丢
            continue
        out.append(
            {
                "text": text,
                "filename": meta.get("filename", "未知"),
                "label": meta.get("label", ""),
                "source_id": meta.get("source_id", ""),
                "similarity": round(similarity, 4),
            }
        )
    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out


# ------------------------------------------------------------------ 管理
def list_sources() -> list[dict]:
    """列出所有已入库文档（按 source_id 聚合，统计片段数）。"""
    col = _col()
    if col.count() == 0:
        return []

    got = col.get(include=["metadatas"])
    metas = got.get("metadatas") or []

    agg: dict[str, dict] = {}
    for meta in metas:
        sid = meta.get("source_id")
        if not sid:
            continue
        if sid not in agg:
            agg[sid] = {
                "source_id": sid,
                "filename": meta.get("filename", "未知"),
                "chunks": 0,
                "uploaded_at": meta.get("uploaded_at", ""),
            }
        agg[sid]["chunks"] += 1

    # 按文件名正序排，用户看到的是 01 / 02 / 03 这种自然顺序
    # （按上传时间倒序会让编号看起来是乱的）
    return sorted(agg.values(), key=lambda x: str(x["filename"]))


def delete_source(source_id: str) -> int:
    """删除某文档的全部切片，返回删除条数。"""
    col = _col()
    before = col.count()
    col.delete(where={"source_id": source_id})
    after = col.count()
    logger.info("已删除 source_id=%s，减少 %s 条", source_id, before - after)
    return before - after


def stats() -> dict:
    """知识库概览。"""
    col = _col()
    sources = list_sources()
    return {
        "documents": len(sources),
        "chunks": col.count(),
        "collection": config.COLLECTION,
        "embedding_model": config.EMBEDDING_MODEL,
        "dim": config.EMBEDDING_DIM,
    }