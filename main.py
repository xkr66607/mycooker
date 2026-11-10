"""
私厨 AI 助手 · RAG 版

启动：
    venv\\Scripts\\python.exe main.py
或：
    venv\\Scripts\\python.exe -m uvicorn main:app --reload --port 8001

架构：
    浏览器 ──SSE──> FastAPI ──> 检索(Chroma) ──> qwen 生成 ──> 流式回传
                      │
                      └──> SQLite（会话历史 + 长期偏好）
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# 保证任何位置启动都能 import 到项目内模块
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config                                    # noqa: E402
from api.v1 import chat, kb, memory              # noqa: E402
from memory.store import init_db                 # noqa: E402
from rag import store as vector_store            # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("mycooker")

app = FastAPI(
    title="私厨 AI 助手 · RAG",
    description="基于知识库检索增强的厨房饮食助手",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    init_db()
    try:
        vector_store.stats()          # 触发 Chroma 初始化并预热
    except Exception as exc:
        logger.warning("向量库初始化异常（可稍后重试）: %s", exc)

    missing = config.assert_ready()
    if missing:
        logger.warning("缺少配置: %s —— 对话功能将不可用", ", ".join(missing))
    else:
        logger.info("配置就绪 | 对话模型=%s | 向量模型=%s",
                    config.CHAT_MODEL, config.EMBEDDING_MODEL)
    logger.info("界面地址: http://%s:%s", config.HOST, config.PORT)


# ---------------------------------------------------------------- 路由
app.include_router(chat.router, prefix="/api/v1", tags=["对话"])
app.include_router(kb.router, prefix="/api/v1", tags=["知识库"])
app.include_router(memory.router, prefix="/api/v1", tags=["记忆"])


@app.get("/api/health")
async def health():
    """健康检查：一眼看出服务到底哪块没配好。"""
    missing = config.assert_ready()
    try:
        st = vector_store.stats()
    except Exception as exc:
        st = {"error": str(exc)}

    return {
        "success": True,
        "ready": not missing,
        "missing_config": missing,
        "models": {
            "chat": config.CHAT_MODEL,
            "vision": config.VISION_MODEL,
            "embedding": config.EMBEDDING_MODEL,
        },
        "knowledge_base": st,
        "version": app.version,
    }


# ---------------------------------------------------------------- 前端静态文件
# 注意：静态挂载必须放在所有 API 路由之后，否则会把 /api 也吞掉
STATIC_DIR = ROOT / "static"
STATIC_DIR.mkdir(exist_ok=True)


@app.get("/", include_in_schema=False)
async def index():
    page = STATIC_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"message": "前端页面缺失：static/index.html 不存在"})


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(config.UPLOAD_DIR)), name="uploads")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host=config.HOST, port=config.PORT, reload=False)