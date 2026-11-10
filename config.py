"""
集中配置 —— 所有可调参数都在这里，改行为不用翻代码。

设计原则：
1. 全部从 .env 读取，带合理默认值，缺配置也能起服务（降级为提示而不是崩溃）
2. 路径全部基于项目根目录推导，不依赖启动时的工作目录
3. 分组清晰：模型 / 切分 / 检索 / 记忆 / 存储
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------- 路径
ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
CHROMA_DIR = DATA_DIR / "chroma"
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "mycooker.db"

for _d in (DATA_DIR, CHROMA_DIR, UPLOAD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- 模型
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
DASHSCOPE_BASE_URL = (
    os.getenv("DASHSCOPE_BASE_URL") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
).strip()

# 对话模型 / 视觉模型 / 向量模型
CHAT_MODEL = os.getenv("MYCOOKER_CHAT_MODEL", "qwen-plus")
VISION_MODEL = os.getenv("MYCOOKER_VISION_MODEL", "qwen-vl-plus")
EMBEDDING_MODEL = os.getenv("MYCOOKER_EMBEDDING_MODEL", "text-embedding-v4")
EMBEDDING_DIM = int(os.getenv("MYCOOKER_EMBEDDING_DIM", "1024"))

# DashScope 原生 embedding 接口（与 OpenAI 兼容接口不是同一个地址）
EMBEDDING_URL = os.getenv(
    "MYCOOKER_EMBEDDING_URL",
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
)
# 单次最多多少条文本送 embed（官方限制 25，留点余量）
EMBEDDING_BATCH = int(os.getenv("MYCOOKER_EMBEDDING_BATCH", "10"))

# ---------------------------------------------------------------- 切分
CHUNK_SIZE = int(os.getenv("MYCOOKER_CHUNK_SIZE", "350"))
CHUNK_OVERLAP = int(os.getenv("MYCOOKER_CHUNK_OVERLAP", "60"))
MAX_FILE_MB = int(os.getenv("MYCOOKER_MAX_FILE_MB", "20"))
ALLOWED_SUFFIX = {".txt", ".md", ".markdown", ".pdf", ".docx", ".csv", ".json"}

# ---------------------------------------------------------------- 检索
TOP_K = int(os.getenv("MYCOOKER_TOP_K", "5"))
# 低于这个余弦相似度的片段直接丢弃（0~1，越高越严格）
# 0.38 是实测出来的：低于这个值的片段基本是"同文档但不同主题"，送进去只会干扰
MIN_SCORE = float(os.getenv("MYCOOKER_MIN_SCORE", "0.38"))
# 送进 prompt 的上下文字符上限，防止撑爆上下文
MAX_CONTEXT_CHARS = int(os.getenv("MYCOOKER_MAX_CONTEXT_CHARS", "6000"))

# ---------------------------------------------------------------- 记忆
HISTORY_TURNS = int(os.getenv("MYCOOKER_HISTORY_TURNS", "6"))
MAX_FACTS = int(os.getenv("MYCOOKER_MAX_FACTS", "30"))

# ---------------------------------------------------------------- 服务
HOST = os.getenv("MYCOOKER_HOST", "127.0.0.1")
PORT = int(os.getenv("MYCOOKER_PORT", "8001"))

COLLECTION = os.getenv("MYCOOKER_COLLECTION", "mycooker_kb")


def assert_ready() -> list[str]:
    """返回缺失的关键配置项，空列表表示就绪。"""
    missing = []
    if not DASHSCOPE_API_KEY:
        missing.append("DASHSCOPE_API_KEY")
    return missing