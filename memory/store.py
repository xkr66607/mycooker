"""
记忆层：把"这一轮聊了什么"和"这个人长期是什么口味"分开存。

为什么分两张表：
- messages  → 短期记忆，按会话追加，用于多轮上下文
- facts     → 长期记忆，跨会话有效（忌口、过敏、口味偏好），条数要控制

两者拼进 prompt 的位置和目的都不同，混在一起会互相挤占上下文。
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime

import config

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '新对话',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    citations       TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS facts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    category   TEXT NOT NULL DEFAULT 'general',
    key        TEXT NOT NULL DEFAULT '',
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_fact_unique ON facts(category, key, value);
"""


@contextmanager
def _conn():
    """每次操作独立连接，开启 WAL 与外键，用完即关。"""
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)
    logger.info("记忆库就绪: %s", config.DB_PATH)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ------------------------------------------------------------------ 会话
def create_conversation(title: str = "新对话") -> str:
    cid = uuid.uuid4().hex[:12]
    ts = _now()
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversations(id, title, created_at, updated_at) VALUES(?,?,?,?)",
            (cid, title.strip() or "新对话", ts, ts),
        )
    return cid


def ensure_conversation(cid: str | None, first_message: str = "") -> str:
    """有就给，没有就建；顺带用首句自动命名。"""
    if cid:
        with _conn() as conn:
            row = conn.execute("SELECT id FROM conversations WHERE id=?", (cid,)).fetchone()
        if row:
            return cid
    title = (first_message or "新对话").strip()[:24]
    return create_conversation(title)


def list_conversations() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT c.id, c.title, c.created_at, c.updated_at,
                      (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS msgs
               FROM conversations c ORDER BY c.updated_at DESC LIMIT 100"""
        ).fetchall()
    return [dict(r) for r in rows]


def delete_conversation(cid: str) -> int:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id=?", (cid,))
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
    return cur.rowcount


# ------------------------------------------------------------------ 消息
def add_message(cid: str, role: str, content: str, citations: list | None = None) -> int:
    import json

    ts = _now()
    with _conn() as conn:
        cur = conn.execute(
            "INSERT INTO messages(conversation_id, role, content, citations, created_at) VALUES(?,?,?,?,?)",
            (cid, role, content, json.dumps(citations or [], ensure_ascii=False), ts),
        )
        conn.execute("UPDATE conversations SET updated_at=? WHERE id=?", (ts, cid))
    return cur.lastrowid


def get_messages(cid: str) -> list[dict]:
    import json

    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content, citations, created_at FROM messages WHERE conversation_id=? ORDER BY id",
            (cid,),
        ).fetchall()
    out = []
    for r in rows:
        try:
            cites = json.loads(r["citations"])
        except Exception:
            cites = []
        out.append(
            {
                "role": r["role"],
                "content": r["content"],
                "citations": cites,
                "created_at": r["created_at"],
            }
        )
    return out


def get_history(cid: str, turns: int | None = None) -> list[dict]:
    """取最近 N 轮对话，供 prompt 使用（不含 citations）。"""
    turns = turns or config.HISTORY_TURNS
    msgs = get_messages(cid)
    limit = turns * 2
    recent = msgs[-limit:] if len(msgs) > limit else msgs
    return [{"role": m["role"], "content": m["content"]} for m in recent]


# ------------------------------------------------------------------ 长期偏好
def add_fact(value: str, category: str = "general", key: str = "") -> dict | None:
    """写一条长期记忆；已存在则只刷新时间。"""
    value = (value or "").strip()
    if not value:
        return None
    ts = _now()
    with _conn() as conn:
        row = conn.execute(
            "SELECT id FROM facts WHERE category=? AND key=? AND value=?",
            (category, key, value),
        ).fetchone()
        if row:
            conn.execute("UPDATE facts SET updated_at=? WHERE id=?", (ts, row["id"]))
            fid = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO facts(category, key, value, created_at, updated_at) VALUES(?,?,?,?,?)",
                (category, key, value, ts, ts),
            )
            fid = cur.lastrowid
    return {"id": fid, "category": category, "key": key, "value": value}


def list_facts(limit: int | None = None) -> list[dict]:
    limit = limit or config.MAX_FACTS
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, category, key, value, created_at, updated_at FROM facts ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_fact(fid: int) -> int:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM facts WHERE id=?", (fid,))
    return cur.rowcount


def facts_as_prompt(limit: int | None = None) -> str:
    """把长期偏好渲染成 prompt 里的一段文本。"""
    facts = list_facts(limit)
    if not facts:
        return ""
    lines = []
    for f in facts:
        tag = f"{f['category']}/{f['key']}" if f["key"] else f["category"]
        lines.append(f"- [{tag}] {f['value']}")
    return "\n".join(lines)