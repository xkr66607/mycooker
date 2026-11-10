"""
知识库入库服务：文件字节 → 解析 → 切分 → 向量化 → 入 Chroma。

这里是同步的（CPU/IO 阻塞），由 API 层用线程池调用。
"""
from __future__ import annotations

import logging
import re

import config
from rag import embeddings, splitter, store

logger = logging.getLogger(__name__)


def _safe_name(filename: str) -> str:
    """只保留安全字符，防止路径穿越（../../etc/passwd 这类）。"""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^\w\u4e00-\u9fa5.\-]", "_", name)
    return name[:120] or "unnamed"


def ingest(filename: str, raw: bytes) -> dict:
    """完整入库流程。抛出的异常由 API 层转成 400/500。"""
    if not raw:
        raise ValueError("文件内容为空")

    size_mb = len(raw) / (1024 * 1024)
    if size_mb > config.MAX_FILE_MB:
        raise ValueError(f"文件过大（{size_mb:.1f}MB），上限 {config.MAX_FILE_MB}MB")

    safe = _safe_name(filename)
    suffix = ("." + safe.rsplit(".", 1)[-1].lower()) if "." in safe else ""
    if suffix not in config.ALLOWED_SUFFIX:
        allowed = "、".join(sorted(config.ALLOWED_SUFFIX))
        raise ValueError(f"不支持的文件类型 {suffix or '(无)'}，支持：{allowed}")

    # 1) 解析
    pieces = splitter.parse(safe, raw)
    logger.info("解析 %s: %s 段", safe, len(pieces))

    # 2) 切分
    chunks = splitter.split(pieces)
    logger.info("切分 %s: %s 个片段", safe, len(chunks))

    # 3) 向量化
    vectors = embeddings.embed_documents([c.text for c in chunks])

    # 4) 入库
    meta = store.add_document(safe, chunks, vectors)

    # 5) 原始文件留档，方便用户回看
    (config.UPLOAD_DIR / f"{meta['source_id']}_{safe}").write_bytes(raw)

    meta["pieces"] = len(pieces)
    meta["size_kb"] = round(len(raw) / 1024, 1)
    return meta