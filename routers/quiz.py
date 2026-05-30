"""Quiz scores router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth_utils import get_current_user_id

router = APIRouter()


class QuizScoreBody(BaseModel):
    quiz_id: str
    score: int
    total: int


@router.get("/")
async def list_scores(user_id: int = Depends(get_current_user_id)):
    rows = await db.fetchall(
        "SELECT quiz_id, score, total FROM quiz_scores "
        "WHERE user_id = ? ORDER BY taken_at DESC",
        (user_id,),
    )
    return {r["quiz_id"]: {"score": r["score"], "total": r["total"]} for r in rows}


@router.post("/", status_code=201)
async def save_score(body: QuizScoreBody, user_id: int = Depends(get_current_user_id)):
    await db.execute(
        "INSERT INTO quiz_scores (user_id, quiz_id, score, total) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, quiz_id) DO UPDATE SET "
        "  score = CASE WHEN excluded.score > score THEN excluded.score ELSE score END, "
        "  total = excluded.total, "
        "  taken_at = strftime('%s','now')",
        (user_id, body.quiz_id, body.score, body.total),
    )
    return {"ok": True}
