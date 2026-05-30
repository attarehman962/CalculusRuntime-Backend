"""Bookmarks router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

import db
from auth_utils import get_current_user_id

router = APIRouter()


class BookmarkBody(BaseModel):
    id: str
    title: str
    path: str


@router.get("/")
async def list_bookmarks(user_id: int = Depends(get_current_user_id)):
    rows = await db.fetchall(
        "SELECT bm_id, title, path, added_at FROM bookmarks "
        "WHERE user_id = ? ORDER BY added_at DESC",
        (user_id,),
    )
    return [
        {
            "id": r["bm_id"],
            "title": r["title"],
            "path": r["path"],
            "addedAt": r["added_at"],
        }
        for r in rows
    ]


@router.post("/", status_code=201)
async def add_bookmark(body: BookmarkBody, user_id: int = Depends(get_current_user_id)):
    await db.execute(
        "INSERT INTO bookmarks (user_id, bm_id, title, path) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(user_id, bm_id) DO NOTHING",
        (user_id, body.id, body.title, body.path),
    )
    return {"ok": True}


@router.delete("/{bm_id}")
async def remove_bookmark(bm_id: str, user_id: int = Depends(get_current_user_id)):
    await db.execute(
        "DELETE FROM bookmarks WHERE user_id = ? AND bm_id = ?",
        (user_id, bm_id),
    )
    return {"ok": True}
