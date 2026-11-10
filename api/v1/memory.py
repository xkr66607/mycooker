"""
长期记忆接口：用户口味、忌口、过敏等跨会话有效的信息。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from memory import store as memory

logger = logging.getLogger(__name__)
router = APIRouter()


class FactIn(BaseModel):
    value: str = Field(..., min_length=1, max_length=500)
    category: str = Field("general", max_length=40)
    key: str = Field("", max_length=40)


@router.get("/memory/facts")
async def list_facts():
    return {"success": True, "data": memory.list_facts()}


@router.post("/memory/facts")
async def add_fact(body: FactIn):
    fact = memory.add_fact(body.value, body.category, body.key)
    if not fact:
        raise HTTPException(400, "内容不能为空")
    return {"success": True, "data": fact}


@router.delete("/memory/facts/{fact_id}")
async def remove_fact(fact_id: int):
    n = memory.delete_fact(fact_id)
    if not n:
        raise HTTPException(404, "记忆不存在")
    return {"success": True, "deleted": n}