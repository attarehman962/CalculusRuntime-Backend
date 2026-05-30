import asyncio
import os
from typing import Any, Dict, List, Optional

PROGRESS_DB = os.getenv("PROGRESS_DB", "").strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_KEY)
USE_SUPABASE = SUPABASE_CONFIGURED or PROGRESS_DB == "supabase"

if USE_SUPABASE:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are required when Supabase is enabled"
        )
    from supabase import create_client

    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def _safe_response(resp: Any) -> Any:
    if getattr(resp, "error", None):
        raise RuntimeError(str(resp.error))
    return getattr(resp, "data", None)


async def get_progress(user_id: int) -> Dict[str, Any]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_get_progress_supabase, user_id)
    return await _get_progress_sqlite(user_id)


async def mark_section_complete(user_id: int, section_id: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _mark_section_complete_supabase, user_id, section_id
        )
    return await _mark_section_complete_sqlite(user_id, section_id)


async def unmark_section_complete(user_id: int, section_id: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _unmark_section_complete_supabase, user_id, section_id
        )
    return await _unmark_section_complete_sqlite(user_id, section_id)


# --- SQLite fallback ---------------------------------------------------------

import db


async def _get_progress_sqlite(user_id: int) -> Dict[str, Any]:
    section_rows = await db.fetchall(
        "SELECT section_id FROM sections WHERE user_id = ?", (user_id,)
    )
    completed_sections = {r["section_id"]: True for r in section_rows}

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


async def _mark_section_complete_sqlite(user_id: int, section_id: str) -> None:
    await db.execute(
        "INSERT INTO sections (user_id, section_id) VALUES (?, ?) "
        "ON CONFLICT(user_id, section_id) DO UPDATE SET completed=1",
        (user_id, section_id),
    )


async def _unmark_section_complete_sqlite(user_id: int, section_id: str) -> None:
    await db.execute(
        "DELETE FROM sections WHERE user_id = ? AND section_id = ?",
        (user_id, section_id),
    )


# --- Supabase backend --------------------------------------------------------

if USE_SUPABASE:

    def _get_progress_supabase(user_id: int) -> Dict[str, Any]:
        section_resp = (
            _supabase.from_("sections")
            .select("section_id")
            .eq("user_id", user_id)
            .execute()
        )
        section_rows = _safe_response(section_resp) or []
        completed_sections = {row["section_id"]: True for row in section_rows}

        quiz_resp = (
            _supabase.from_("quiz_scores")
            .select("quiz_id,score,total")
            .eq("user_id", user_id)
            .execute()
        )
        quiz_rows = _safe_response(quiz_resp) or []
        quiz_scores = {
            row["quiz_id"]: {"score": row["score"], "total": row["total"]}
            for row in quiz_rows
        }

        bm_resp = (
            _supabase.from_("bookmarks")
            .select("bm_id,title,path,added_at")
            .eq("user_id", user_id)
            .order("added_at", desc=True)
            .execute()
        )
        bm_rows = _safe_response(bm_resp) or []
        bookmarks = [
            {
                "id": row["bm_id"],
                "title": row["title"],
                "path": row["path"],
                "addedAt": row["added_at"],
            }
            for row in bm_rows
        ]

        solver_resp = (
            _supabase.from_("solver_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        solver_count = getattr(solver_resp, "count", 0) or 0

        return {
            "completedSections": completed_sections,
            "quizScores": quiz_scores,
            "bookmarks": bookmarks,
            "solverUses": solver_count,
        }

    def _mark_section_complete_supabase(user_id: int, section_id: str) -> None:
        resp = (
            _supabase.from_("sections")
            .upsert(
                {"user_id": user_id, "section_id": section_id, "completed": True},
                on_conflict="user_id,section_id",
            )
            .execute()
        )
        _safe_response(resp)

    def _unmark_section_complete_supabase(user_id: int, section_id: str) -> None:
        resp = (
            _supabase.from_("sections")
            .delete()
            .eq("user_id", user_id)
            .eq("section_id", section_id)
            .execute()
        )
        _safe_response(resp)
