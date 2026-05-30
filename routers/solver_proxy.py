"""
Solver proxy + history router.
Records each solve call in solver_history for logged-in users.
The actual solving is done by the hosted Streamlit app; this endpoint
just logs usage and can optionally forward to a local solver API.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth_utils import get_optional_user_id

router = APIRouter()

SOLVER_API_URL = os.getenv("SOLVER_API_URL", "")  # e.g. http://localhost:8001


class SolverLogBody(BaseModel):
    expression: Optional[str] = None
    result: Optional[str] = None


@router.post("/log")
async def log_solver_use(
    body: SolverLogBody,
    user_id: Optional[int] = Depends(get_optional_user_id),
):
    """Called by the frontend after each solver interaction to record history."""
    if user_id:
        await db.execute(
            "INSERT INTO solver_history (user_id, expression, result) VALUES (?, ?, ?)",
            (user_id, body.expression, body.result),
        )
    return {"ok": True}


@router.get("/history")
async def solver_history(user_id: int = Depends(get_optional_user_id)):
    if not user_id:
        return []
    rows = await db.fetchall(
        "SELECT expression, result, created_at FROM solver_history "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )
    return rows
