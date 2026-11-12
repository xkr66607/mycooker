"""
集中配置 —— 所有可调参数都在这里，改行为不用翻代码。

设计原则：
1. 全部从 .env 读取，带合理默认值，缺配置也能起服务（降级为提示而不是崩溃）
2. 路径全部基于项目根目录推导，不依赖启动时的工作目录
3. 分组清晰：模型 / 切分 / 检索 / 记忆 / 存储

⚠️ 模型分三块，各自独立配置，因为不同厂商能力不一样：

    ┌─────────────┬──────────────────────┬──────────────────────────┐
    │ 用途        │ 需要什么能力          │ 能换哪些厂商              │
    ├─────────────┼──────────────────────┼──────────────────────────┤
    │ CHAT_*      │ 文本对话              │ 千问 / DeepSeek / 任意    │
    │ VISION_*    │ 看图（多模态）        │ 千问 qwen-vl / GPT 等  │
    │ EMBEDDING_* │ 把文字变成向量        │ 千问 / OpenAI / BGE 等    │
    └─────────────┴──────────────────────┴──────────────────────────┘

    实测结论：DeepSeek 的 /embeddings 返回 404，它没有向量接口。
    所以「对话换 DeepSeek」可以，「向量换 DeepSeek」不行 —— 向量必须留在千问。
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

# ---------------------------------------------------------------- 通用取值工具
_DEFAULT_DASHSCOPE_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_DASHSCOPE_EMBED = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
)


def _env(*names: str) -> str:
    """按顺序取第一个非空的环境变量值，都没有返回空串。

    支持多个名字是为了向后兼容：新名字优先，旧名字（MYCOOKER_ 前缀）兜底。
    """
    for n in names:
        v = os.getenv(n, "").strip()
        if v:
            return v
    return ""


# ================================================================
# 千问（DashScope）基础凭证 —— 向量模型一直用它，不要动
# ================================================================
DASHSCOPE_API_KEY = _env("DASHSCOPE_API_KEY")
DASHSCOPE_BASE_URL = _env("DASHSCOPE_BASE_URL") or _DEFAULT_DASHSCOPE_BASE

# ================================================================
# 1. 对话模型（CHAT_*）—— 想换 DeepSeek 就改这里
# ================================================================
# 例子 A（默认，用千问）：
#     CHAT_API_KEY   = （留空，自动用 DASHSCOPE_API_KEY）
#     CHAT_BASE_URL  = （留空，自动用 DASHSCOPE_BASE_URL）
#     CHAT_MODEL     = qwen-plus
#
# 例子 B（换成 DeepSeek）：
#     CHAT_API_KEY   = sk-你的DeepSeekKey
#     CHAT_BASE_URL  = https://api.deepseek.com
#     CHAT_MODEL     = deepseek-chat        （或 deepseek-flash / deepseek-v4-pro）
CHAT_API_KEY = _env("CHAT_API_KEY") or DASHSCOPE_API_KEY
CHAT_BASE_URL = (_env("CHAT_BASE_URL") or DASHSCOPE_BASE_URL).rstrip("/")
CHAT_MODEL = _env("CHAT_MODEL", "MYCOOKER_CHAT_MODEL") or "qwen-plus"
# 单次回答的 token 上限。推理模型（deepseek-v4.1-flash / deepseek-reasoner）
# 的思考过程也算在 completion_tokens 里，给太小会出现"只有思考、没有回答"。
CHAT_MAX_TOKENS = int(_env("CHAT_MAX_TOKENS") or "3000")

# ================================================================
# 2. 视觉模型（VISION_*）—— 识别食材照片
# ================================================================
# 实测（2026-11，账号内 182 个模型）：
#   ✘ qwen-vl-plus / qwen-vl-max  已下线，返回 404 —— 旧的默认值踩过这个坑
#   ✔ qwen3-vl-plus               当前主力视觉模型
#   ✔ qwen-vl-ocr                 偏 OCR 场景
#   ✔ deepseek-v4.1-flash         居然也支持视觉（deepseek-v4-pro 不支持）
#
# 另外：如果 CHAT_* 和 VISION_* 都指向 deepseek-v4.1-flash，
#       一个模型就能同时干这两件事，配置可以更简单。
VISION_API_KEY = _env("VISION_API_KEY") or DASHSCOPE_API_KEY
VISION_BASE_URL = (_env("VISION_BASE_URL") or DASHSCOPE_BASE_URL).rstrip("/")
VISION_MODEL = _env("VISION_MODEL", "MYCOOKER_VISION_MODEL") or "qwen3-vl-plus"
# ⚠️ 推理模型的思考过程也占 completion_tokens，而且波动极大。
#    实测 deepseek-v4.1-flash 看同一张图，思考 token 在 1378 ~ 2923 之间跳：
#      max_tokens=1200 → 全被思考吃光，正文 0 字（表现为「图片识别静默失效」）
#      max_tokens=2000 → 有时够有时不够
#      max_tokens=4000 → 大多够，但赶上思考长的时候仍可能不够
#    所以要拿它做视觉，这里必须给很大。
#    非推理模型（qwen3-vl-plus）只用到 29 个 token，设再大也不会浪费。
VISION_MAX_TOKENS = int(_env("VISION_MAX_TOKENS") or "8000")

# ================================================================
# 3. 向量模型（EMBEDDING_*）—— 检索的地基，动了要重建知识库
# ================================================================
# ⚠️ 换 embedding 模型 = 向量维度/语义空间变了 = 旧向量全部作废，必须清库重传。
#    所以这个默认值不要轻易改。
EMBEDDING_API_KEY = _env("EMBEDDING_API_KEY") or DASHSCOPE_API_KEY
EMBEDDING_MODEL = _env("EMBEDDING_MODEL", "MYCOOKER_EMBEDDING_MODEL") or "text-embedding-v4"
EMBEDDING_DIM = int(_env("EMBEDDING_DIM", "MYCOOKER_EMBEDDING_DIM") or "1024")
# DashScope 原生 embedding 接口（注意：和 OpenAI 兼容接口不是同一个地址）
EMBEDDING_URL = _env("EMBEDDING_URL", "MYCOOKER_EMBEDDING_URL") or _DEFAULT_DASHSCOPE_EMBED
# 单次最多多少条文本送 embed（官方限制 25，留点余量）
EMBEDDING_BATCH = int(_env("EMBEDDING_BATCH", "MYCOOKER_EMBEDDING_BATCH") or "10")

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


# ---------------------------------------------------------------- 自检与展示
def _provider_of(base_url: str) -> str:
    """从 base_url 猜厂商名，只用于显示。"""
    u = (base_url or "").lower()
    if "dashscope" in u or "aliyuncs" in u:
        return "千问 DashScope"
    if "deepseek" in u:
        return "DeepSeek"
    if "openai" in u:
        return "OpenAI"
    if "moonshot" in u:
        return "月之暗面"
    if "bigmodel" in u or "zhipu" in u:
        return "智谱"
    if "siliconflow" in u:
        return "硅基流动"
    return base_url or "未知"


def providers() -> dict:
    """当前生效的三块模型服务，给 /api/health 和启动日志用。"""
    return {
        "chat": {
            "provider": _provider_of(CHAT_BASE_URL),
            "model": CHAT_MODEL,
            "base_url": CHAT_BASE_URL,
        },
        "vision": {
            "provider": _provider_of(VISION_BASE_URL),
            "model": VISION_MODEL,
            "base_url": VISION_BASE_URL,
        },
        "embedding": {
            "provider": _provider_of(EMBEDDING_URL),
            "model": EMBEDDING_MODEL,
            "dim": EMBEDDING_DIM,
        },
    }


def summary() -> str:
    """一行式描述，打日志用。"""
    p = providers()
    return (
        f"对话={p['chat']['provider']}/{p['chat']['model']} | "
        f"视觉={p['vision']['provider']}/{p['vision']['model']} | "
        f"向量={p['embedding']['provider']}/{p['embedding']['model']}({EMBEDDING_DIM}维)"
    )


def assert_ready() -> list[str]:
    """返回缺失的关键配置项，空列表表示就绪。"""
    missing = []
    if not CHAT_API_KEY:
        missing.append("CHAT_API_KEY（或 DASHSCOPE_API_KEY）")
    if not EMBEDDING_API_KEY:
        missing.append("EMBEDDING_API_KEY（或 DASHSCOPE_API_KEY）")
    if not VISION_API_KEY:
        missing.append("VISION_API_KEY（或 DASHSCOPE_API_KEY）")
    return missing


def warnings() -> list[str]:
    """不致命但值得提醒的问题。"""
    out = []
    # DeepSeek 官方 API（api.deepseek.com）没有 embedding 接口，配错了入库会 404
    if "deepseek" in EMBEDDING_URL.lower():
        out.append(
            "EMBEDDING_URL 指向了 DeepSeek，但它没有向量接口（/embeddings 返回 404）。"
            "向量模型请继续使用千问 text-embedding-v4。"
        )
    # 已下线的模型，用了会直接 404
    if VISION_MODEL in ("qwen-vl-plus", "qwen-vl-max"):
        out.append(
            f"视觉模型 {VISION_MODEL} 已下线（404），请改成 qwen3-vl-plus"
            " 或 deepseek-v4.1-flash。"
        )
    # deepseek-v4-pro 没有视觉能力，拿它当视觉模型会失败
    if "deepseek-v4-pro" in VISION_MODEL:
        out.append(
            "deepseek-v4-pro 不支持视觉，识别食材照片会失败。"
            "要视觉请用 deepseek-v4.1-flash 或 qwen3-vl-plus。"
        )
    # 拿推理模型做视觉，思考 token 会吃掉配额，容易得到空正文
    if "deepseek" in VISION_MODEL and VISION_MAX_TOKENS < 6000:
        out.append(
            f"VISION_MODEL={VISION_MODEL} 是推理模型，看一张图会先花 1400~3000 个思考 token。"
            f"当前 VISION_MAX_TOKENS={VISION_MAX_TOKENS} 可能不够，建议 ≥ 8000，"
            "或者视觉改用 qwen3-vl-plus（同任务只花 29 个 token）。"
        )
    # 两边是同一家但用了不同 key，通常是误配
    if (
        _provider_of(CHAT_BASE_URL) == _provider_of(EMBEDDING_URL)
        and CHAT_API_KEY
        and EMBEDDING_API_KEY
        and CHAT_API_KEY != EMBEDDING_API_KEY
    ):
        out.append("CHAT_API_KEY 和 EMBEDDING_API_KEY 指向同一家服务但 Key 不同，请确认是否有意为之。")
    return out