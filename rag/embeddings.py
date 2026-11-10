"""
Embedding 封装 —— 把文本变成向量。

为什么单独一层：
- 外部 API 会抖动，必须有重试
- 一次请求有条数上限，必须分批
- 返回顺序不保证，必须按 text_index 还原

这一层做到"调用方不用关心这些"，上层只管传一段一段文本、拿回一组向量。
"""
from __future__ import annotations

import logging
import time

import requests

import config

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """向量化失败，上层应捕获并降级。"""


def _request(texts: list[str], text_type: str, retries: int = 3) -> list[list[float]]:
    """调一次 DashScope embedding 接口，失败自动重试（指数退避）。"""
    if not config.DASHSCOPE_API_KEY:
        raise EmbeddingError("缺少 DASHSCOPE_API_KEY，无法向量化")

    payload = {
        "model": config.EMBEDDING_MODEL,
        "input": {"texts": texts},
        "parameters": {"dimension": config.EMBEDDING_DIM, "text_type": text_type},
    }
    headers = {
        "Authorization": f"Bearer {config.DASHSCOPE_API_KEY}",
        "Content-Type": "application/json",
    }

    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(
                config.EMBEDDING_URL, headers=headers, json=payload, timeout=60
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("output", {}).get("embeddings", [])
                if not items:
                    raise EmbeddingError(f"接口返回空结果: {str(data)[:200]}")
                # 按 text_index 还原顺序，避免分批并发时错位
                items = sorted(items, key=lambda x: x.get("text_index", 0))
                return [it["embedding"] for it in items]

            # 429 / 5xx 值得重试，4xx 其它错误重试也没用
            last_err = f"HTTP {resp.status_code}: {resp.text[:300]}"
            if resp.status_code not in (429, 500, 502, 503, 504):
                raise EmbeddingError(last_err)
        except requests.RequestException as exc:
            last_err = f"{type(exc).__name__}: {exc}"

        if attempt < retries:
            wait = 2 ** attempt
            logger.warning("embedding 第 %s 次失败(%s)，%ss 后重试", attempt, last_err, wait)
            time.sleep(wait)

    raise EmbeddingError(f"向量化失败，已重试 {retries} 次: {last_err}")


def embed_documents(texts: list[str]) -> list[list[float]]:
    """把知识库文档切片转成向量（入库时用）。"""
    return _embed(texts, text_type="document")


def embed_query(text: str) -> list[float]:
    """把用户问题转成向量（检索时用）。"""
    vecs = _embed([text], text_type="query")
    return vecs[0]


def _embed(texts: list[str], text_type: str) -> list[list[float]]:
    """按批切分后逐批请求，合并结果，保证输入输出一一对应。"""
    clean = [(t or "").strip() for t in texts]
    # 空串会被接口拒绝，用单个空格占位；同时记录原始索引以便还原
    pairs = [(i, t if t else " ") for i, t in enumerate(clean)]

    out: list[list[float]] = [[] for _ in clean]
    batch = max(1, config.EMBEDDING_BATCH)

    for start in range(0, len(pairs), batch):
        chunk = pairs[start : start + batch]
        vecs = _request([t for _, t in chunk], text_type)
        if len(vecs) != len(chunk):
            raise EmbeddingError(f"向量数量不匹配: 期望 {len(chunk)}, 实际 {len(vecs)}")
        for (orig_idx, _), vec in zip(chunk, vecs):
            out[orig_idx] = vec

    return out