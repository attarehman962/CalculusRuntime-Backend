import asyncio
import os
from typing import Any, Dict, Optional

import db


DB_BACKEND = (
    os.getenv("DB_BACKEND")
    or os.getenv("DATABASE_BACKEND")
    or os.getenv("PROGRESS_DB")
    or ""
).strip().lower()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SECRET_KEY")
    or os.getenv("SUPABASE_KEY")
    or ""
).strip()
USE_SUPABASE = DB_BACKEND == "supabase" or bool(SUPABASE_URL and SUPABASE_KEY)

if USE_SUPABASE:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are required when Supabase is enabled."
        )

    from supabase import create_client

    if SUPABASE_KEY.startswith("sb_publishable_"):
        print(
            "[CalcVoyager] Warning: SUPABASE_KEY is a publishable key. "
            "Use SUPABASE_SERVICE_ROLE_KEY for backend writes, or disable RLS "
            "on the app tables in backend/supabase_schema.sql.",
            flush=True,
        )

    _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def _data(resp: Any) -> Any:
    if getattr(resp, "error", None):
        raise RuntimeError(str(resp.error))
    return getattr(resp, "data", None)


async def init_storage() -> None:
    if USE_SUPABASE:
        return None
    await db.init_db()


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_get_user_by_username_supabase, username)
    return await db.fetchone(
        "SELECT id, username, hashed_pw FROM users WHERE username = ?", (username,)
    )


async def create_user(username: str, email: Optional[str], hashed_pw: str) -> int:
    if USE_SUPABASE:
        return await asyncio.to_thread(_create_user_supabase, username, email, hashed_pw)
    return await db.execute(
        "INSERT INTO users (username, email, hashed_pw) VALUES (?, ?, ?)",
        (username, email, hashed_pw),
    )


async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_get_user_profile_supabase, user_id)
    return await db.fetchone(
        "SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)
    )


async def get_progress(user_id: int) -> Dict[str, Any]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_get_progress_supabase, user_id)
    return await _get_progress_sqlite(user_id)


async def mark_section_complete(user_id: int, section_id: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _mark_section_complete_supabase, user_id, section_id
        )
    await db.execute(
        "INSERT INTO sections (user_id, section_id) VALUES (?, ?) "
        "ON CONFLICT(user_id, section_id) DO UPDATE SET completed=1",
        (user_id, section_id),
    )


async def unmark_section_complete(user_id: int, section_id: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _unmark_section_complete_supabase, user_id, section_id
        )
    await db.execute(
        "DELETE FROM sections WHERE user_id = ? AND section_id = ?",
        (user_id, section_id),
    )


async def list_bookmarks(user_id: int) -> list[Dict[str, Any]]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_list_bookmarks_supabase, user_id)
    rows = await db.fetchall(
        "SELECT bm_id, title, path, added_at FROM bookmarks "
        "WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,),
    )
    return [_bookmark_json(row) for row in rows]


async def add_bookmark(user_id: int, bm_id: str, title: str, path: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _add_bookmark_supabase, user_id, bm_id, title, path
        )
    await db.execute(
        "INSERT INTO bookmarks (user_id, bm_id, title, path) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, bm_id) DO NOTHING",
        (user_id, bm_id, title, path),
    )


async def remove_bookmark(user_id: int, bm_id: str) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(_remove_bookmark_supabase, user_id, bm_id)
    await db.execute(
        "DELETE FROM bookmarks WHERE user_id = ? AND bm_id = ?",
        (user_id, bm_id),
    )


async def list_quiz_scores(user_id: int) -> Dict[str, Dict[str, int]]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_list_quiz_scores_supabase, user_id)
    rows = await db.fetchall(
        "SELECT quiz_id, score, total FROM quiz_scores "
        "WHERE user_id = ? ORDER BY taken_at DESC",
        (user_id,),
    )
    return {
        row["quiz_id"]: {"score": row["score"], "total": row["total"]}
        for row in rows
    }


async def save_quiz_score(user_id: int, quiz_id: str, score: int, total: int) -> None:
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _save_quiz_score_supabase, user_id, quiz_id, score, total
        )
    await db.execute(
        "INSERT INTO quiz_scores (user_id, quiz_id, score, total) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, quiz_id) DO UPDATE SET "
        "  score = CASE WHEN excluded.score > score THEN excluded.score ELSE score END, "
        "  total = excluded.total, "
        "  taken_at = strftime('%s','now')",
        (user_id, quiz_id, score, total),
    )


async def log_solver_use(
    user_id: Optional[int], expression: Optional[str], result: Optional[str]
) -> None:
    if not user_id:
        return None
    if USE_SUPABASE:
        return await asyncio.to_thread(
            _log_solver_use_supabase, user_id, expression, result
        )
    await db.execute(
        "INSERT INTO solver_history (user_id, expression, result) VALUES (?, ?, ?)",
        (user_id, expression, result),
    )


async def list_solver_history(user_id: int) -> list[Dict[str, Any]]:
    if USE_SUPABASE:
        return await asyncio.to_thread(_list_solver_history_supabase, user_id)
    return await db.fetchall(
        "SELECT expression, result, created_at FROM solver_history "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 50",
        (user_id,),
    )


async def _get_progress_sqlite(user_id: int) -> Dict[str, Any]:
    section_rows = await db.fetchall(
        "SELECT section_id FROM sections WHERE user_id = ?", (user_id,)
    )
    solver_count = (
        await db.scalar(
            "SELECT COUNT(*) FROM solver_history WHERE user_id = ?", (user_id,)
        )
        or 0
    )

    return {
        "completedSections": {row["section_id"]: True for row in section_rows},
        "quizScores": await list_quiz_scores(user_id),
        "bookmarks": await list_bookmarks(user_id),
        "solverUses": solver_count,
    }


def _first(resp: Any) -> Optional[Dict[str, Any]]:
    rows = _data(resp) or []
    return rows[0] if rows else None


def _bookmark_json(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": row["bm_id"],
        "title": row["title"],
        "path": row["path"],
        "addedAt": row["added_at"],
    }


if USE_SUPABASE:

    def _get_user_by_username_supabase(username: str) -> Optional[Dict[str, Any]]:
        resp = (
            _supabase.from_("users")
            .select("id,username,hashed_pw")
            .eq("username", username)
            .limit(1)
            .execute()
        )
        return _first(resp)

    def _create_user_supabase(
        username: str, email: Optional[str], hashed_pw: str
    ) -> int:
        payload = {"username": username, "email": email, "hashed_pw": hashed_pw}
        resp = _supabase.from_("users").insert(payload).execute()
        rows = _data(resp) or []
        if not rows:
            raise RuntimeError("Supabase did not return the created user.")
        return int(rows[0]["id"])

    def _get_user_profile_supabase(user_id: int) -> Optional[Dict[str, Any]]:
        resp = (
            _supabase.from_("users")
            .select("id,username,email,created_at")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return _first(resp)

    def _get_progress_supabase(user_id: int) -> Dict[str, Any]:
        section_resp = (
            _supabase.from_("sections")
            .select("section_id")
            .eq("user_id", user_id)
            .execute()
        )
        section_rows = _data(section_resp) or []

        solver_resp = (
            _supabase.from_("solver_history")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )

        return {
            "completedSections": {
                row["section_id"]: True for row in section_rows
            },
            "quizScores": _list_quiz_scores_supabase(user_id),
            "bookmarks": _list_bookmarks_supabase(user_id),
            "solverUses": getattr(solver_resp, "count", 0) or 0,
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
        _data(resp)

    def _unmark_section_complete_supabase(user_id: int, section_id: str) -> None:
        resp = (
            _supabase.from_("sections")
            .delete()
            .eq("user_id", user_id)
            .eq("section_id", section_id)
            .execute()
        )
        _data(resp)

    def _list_bookmarks_supabase(user_id: int) -> list[Dict[str, Any]]:
        resp = (
            _supabase.from_("bookmarks")
            .select("bm_id,title,path,added_at")
            .eq("user_id", user_id)
            .order("added_at", desc=True)
            .execute()
        )
        return [_bookmark_json(row) for row in (_data(resp) or [])]

    def _add_bookmark_supabase(
        user_id: int, bm_id: str, title: str, path: str
    ) -> None:
        resp = (
            _supabase.from_("bookmarks")
            .upsert(
                {"user_id": user_id, "bm_id": bm_id, "title": title, "path": path},
                on_conflict="user_id,bm_id",
            )
            .execute()
        )
        _data(resp)

    def _remove_bookmark_supabase(user_id: int, bm_id: str) -> None:
        resp = (
            _supabase.from_("bookmarks")
            .delete()
            .eq("user_id", user_id)
            .eq("bm_id", bm_id)
            .execute()
        )
        _data(resp)

    def _list_quiz_scores_supabase(user_id: int) -> Dict[str, Dict[str, int]]:
        resp = (
            _supabase.from_("quiz_scores")
            .select("quiz_id,score,total")
            .eq("user_id", user_id)
            .order("taken_at", desc=True)
            .execute()
        )
        return {
            row["quiz_id"]: {"score": row["score"], "total": row["total"]}
            for row in (_data(resp) or [])
        }

    def _save_quiz_score_supabase(
        user_id: int, quiz_id: str, score: int, total: int
    ) -> None:
        existing_resp = (
            _supabase.from_("quiz_scores")
            .select("score")
            .eq("user_id", user_id)
            .eq("quiz_id", quiz_id)
            .limit(1)
            .execute()
        )
        existing = _first(existing_resp)
        best_score = max(score, int(existing["score"])) if existing else score
        resp = (
            _supabase.from_("quiz_scores")
            .upsert(
                {
                    "user_id": user_id,
                    "quiz_id": quiz_id,
                    "score": best_score,
                    "total": total,
                },
                on_conflict="user_id,quiz_id",
            )
            .execute()
        )
        _data(resp)

    def _log_solver_use_supabase(
        user_id: int, expression: Optional[str], result: Optional[str]
    ) -> None:
        resp = (
            _supabase.from_("solver_history")
            .insert(
                {"user_id": user_id, "expression": expression, "result": result}
            )
            .execute()
        )
        _data(resp)

    def _list_solver_history_supabase(user_id: int) -> list[Dict[str, Any]]:
        resp = (
            _supabase.from_("solver_history")
            .select("expression,result,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(50)
            .execute()
        )
        return _data(resp) or []
