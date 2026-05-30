"""Progress router — full snapshot, mark/unmark sections."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth_utils import get_current_user_id

router = APIRouter()


class SectionBody(BaseModel):
    section_id: str


@router.get("/")
async def get_progress(user_id: int = Depends(get_current_user_id)):
    """Full progress snapshot — sections, quiz scores, bookmarks, solver count."""

    sections_rows = await db.fetchall(
        "SELECT section_id FROM sections WHERE user_id = ?", (user_id,)
    )
    completed_sections = {r["section_id"]: True for r in sections_rows}

    quiz_rows = await db.fetchall(
        "SELECT quiz_id, score, total FROM quiz_scores WHERE user_id = ?", (user_id,)
    )
    quiz_scores = {
        r["quiz_id"]: {"score": r["score"], "total": r["total"]} for r in quiz_rows
    }

    bm_rows = await db.fetchall(
        "SELECT bm_id, title, path, added_at FROM bookmarks "
        "WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,),
    )
    bookmarks = [
        {
            "id": r["bm_id"],
            "title": r["title"],
            "path": r["path"],
            "addedAt": r["added_at"],
        }
        for r in bm_rows
    ]

    solver_count = (
        await db.scalar(
            "SELECT COUNT(*) FROM solver_history WHERE user_id = ?", (user_id,)
        )
        or 0
    )

    return {
        "completedSections": completed_sections,
        "quizScores": quiz_scores,
        "bookmarks": bookmarks,
        "solverUses": solver_count,
    }


@router.post("/section/complete")
async def mark_complete(body: SectionBody, user_id: int = Depends(get_current_user_id)):
    await db.execute(
        "INSERT INTO sections (user_id, section_id) VALUES (?, ?) "
        "ON CONFLICT(user_id, section_id) DO UPDATE SET completed=1",
        (user_id, body.section_id),
    )
    return {"ok": True, "section_id": body.section_id}


@router.delete("/section/{section_id}")
async def unmark_complete(section_id: str, user_id: int = Depends(get_current_user_id)):
    await db.execute(
        "DELETE FROM sections WHERE user_id = ? AND section_id = ?",
        (user_id, section_id),
    )
    return {"ok": True}
