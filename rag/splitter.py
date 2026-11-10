"""
文档解析 + 切分。

为什么切分方式决定 RAG 的成败：
向量是一条"平均语义"。如果一块 500 字里混着"鸡蛋怎么炒"和"糖醋汁比例"，
它的向量就是两者的平均，检索任何一个都只能命中一半精度。
所以切分的首要目标不是"切得匀"，而是"每块只讲一件事"。

本模块的策略（两级切分）：
1. 先按 Markdown 标题切"节" —— 天然的主题边界，作者已经帮我们划好了
2. 节内如果还是太长，再用递归字符切分按句号/换行细分
3. 每个片段都把"所属章节标题"拼在正文前面，让向量带上主题上下文

效果：问"糖醋汁比例"能精确命中"六、调味的基本比例"那一节，
而不是命中"鸡蛋冷藏"。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

import config

logger = logging.getLogger(__name__)

# 中文优先的分隔符：先按段落，再按句号，最后才按空格/字符兜底
SEPARATORS = ["\n\n", "\n", "。", "！", "？", "；", "…", ".", "!", "?", ";", " ", ""]

# Markdown 标题：# / ## / ### ...（行首，后面跟空格）
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class Piece:
    """解析出来的一段原文（PDF 按页、Markdown 按节、txt 整体）。"""
    label: str      # 展示给用户的来源位置，如 "第 3 页" / "六、调味的基本比例"
    text: str


@dataclass
class Chunk:
    """切分后的最小检索单元。"""
    text: str       # 送去做 embedding 的文本（含标题前缀）
    label: str      # 来源位置，展示给用户
    index: int      # 在原文中的顺序，用于稳定排序


# ------------------------------------------------------------------ 解析
def parse(filename: str, raw: bytes) -> list[Piece]:
    """根据扩展名选择解析方式，返回带位置标记的文本段。"""
    suffix = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if suffix in (".txt",):
        return [Piece("全文", _decode(raw))]

    if suffix in (".md", ".markdown"):
        return _parse_markdown(_decode(raw))

    if suffix == ".pdf":
        return _parse_pdf(raw)

    if suffix == ".docx":
        return _parse_docx(raw)

    if suffix == ".csv":
        return _parse_csv(raw)

    if suffix == ".json":
        return _parse_json(raw)

    raise ValueError(f"暂不支持的文件类型: {suffix or '(无扩展名)'}")


def _decode(raw: bytes) -> str:
    """尽量宽容地解码：先 utf-8，再 gbk，最后忽略错误。"""
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _parse_markdown(text: str) -> list[Piece]:
    """
    按标题切成节。每节的 label 是标题路径（如"六、调味的基本比例"）。
    没有标题的文档退化为整体一段。
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        # 没有 Markdown 结构时，尝试用"一、二、三"这类中文序号切
        return _split_by_chinese_numbering(text)

    pieces: list[Piece] = []
    # 第一个标题之前的内容（通常是文档说明）
    preamble = text[: matches[0].start()].strip()
    if preamble:
        pieces.append(Piece("文档说明", preamble))

    for i, m in enumerate(matches):
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            pieces.append(Piece(title, body))

    return pieces or [Piece("全文", text)]


def _split_by_chinese_numbering(text: str) -> list[Piece]:
    """纯 txt 里常见"一、xxx 二、xxx"结构，按它切节，效果远好于整篇当一块。"""
    pattern = re.compile(r"(?m)^\s*([一二三四五六七八九十]+[、.．]\s*.{0,30})$")
    matches = list(pattern.finditer(text))
    if len(matches) < 2:          # 少于 2 个标题就不折腾了
        return [Piece("全文", text)]

    pieces: list[Piece] = []
    head = text[: matches[0].start()].strip()
    if head:
        pieces.append(Piece("开头", head))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            pieces.append(Piece(title[:40], body))
    return pieces or [Piece("全文", text)]


def _parse_pdf(raw: bytes) -> list[Piece]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    pieces: list[Piece] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("PDF 第 %s 页解析失败: %s", i, exc)
            text = ""
        if text.strip():
            pieces.append(Piece(f"第 {i} 页", text))
    if not pieces:
        raise ValueError("PDF 中没有可提取的文字（可能是扫描件，需要 OCR）")
    return pieces


def _parse_docx(raw: bytes) -> list[Piece]:
    import docx

    document = docx.Document(io.BytesIO(raw))
    parts: list[str] = []
    for para in document.paragraphs:
        if para.text.strip():
            # 标题样式转换成 Markdown 井号，复用后续按节切分逻辑
            style = (para.style.name or "").lower()
            if "heading" in style or style.startswith("标题"):
                level = "".join(ch for ch in style if ch.isdigit()) or "1"
                parts.append("#" * min(int(level), 6) + " " + para.text.strip())
            else:
                parts.append(para.text)
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    text = "\n".join(parts)
    if not text.strip():
        raise ValueError("Word 文档中没有可提取的文字")
    return _parse_markdown(text)


def _parse_csv(raw: bytes) -> list[Piece]:
    text = _decode(raw)
    reader = csv.reader(io.StringIO(text))
    rows = [" | ".join(c.strip() for c in row) for row in reader if any(c.strip() for c in row)]
    if not rows:
        raise ValueError("CSV 为空")
    return [Piece("表格", "\n".join(rows))]


def _parse_json(raw: bytes) -> list[Piece]:
    data = json.loads(_decode(raw))
    return [Piece("全文", json.dumps(data, ensure_ascii=False, indent=2))]


# ------------------------------------------------------------------ 切分
def split(pieces: list[Piece]) -> list[Chunk]:
    """
    节内再切：只处理超长节。
    每个片段的 text 会拼上【章节标题】，让向量带上主题上下文。
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
        separators=SEPARATORS,
        length_function=len,
        keep_separator=True,
    )

    chunks: list[Chunk] = []
    idx = 0
    for piece in pieces:
        body = piece.text.strip()
        if not body:
            continue

        segs = [body] if len(body) <= config.CHUNK_SIZE else splitter.split_text(body)
        for seg in segs:
            seg = seg.strip()
            if len(seg) < 12:            # 丢掉页眉页码这类碎片
                continue
            # 把标题拼进正文，作为 embedding 的语义锚点
            prefix = f"【{piece.label}】" if piece.label and piece.label != "全文" else ""
            chunks.append(Chunk(text=f"{prefix}{seg}", label=piece.label, index=idx))
            idx += 1

    if not chunks:
        raise ValueError("切分后没有有效内容，请检查文档是否为空")
    return chunks