"""Progress routes — full snapshot, mark/unmark sections."""

from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse

from progress_store import get_progress, mark_section_complete, unmark_section_complete
from auth_utils import require_user, err


async def get_progress_route(request: Request):
    user_id = require_user(request)
    if not user_id:
        return err(401, "Not authenticated.")

    progress = await get_progress(user_id)
    return JSONResponse(progress)


async def mark_complete(request: Request):
    user_id = require_user(request)
    if not user_id:
        return err(401, "Not authenticated.")
    try:
        body = await request.json()
    except Exception:
        return err(400, "Invalid JSON.")

    section_id = (body.get("section_id") or "").strip()
    if not section_id:
        return err(400, "section_id required.")

    await mark_section_complete(user_id, section_id)
    return JSONResponse({"ok": True, "section_id": section_id})


async def unmark_complete(request: Request):
    user_id = require_user(request)
    if not user_id:
        return err(401, "Not authenticated.")

    section_id = request.path_params.get("section_id", "")
    await unmark_section_complete(user_id, section_id)
    return JSONResponse({"ok": True})


routes = [
    Route("/", get_progress_route, methods=["GET"]),
    Route("/section/complete", mark_complete, methods=["POST"]),
    Route("/section/{section_id}", unmark_complete, methods=["DELETE"]),
]
