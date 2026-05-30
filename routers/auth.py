"""Auth router — signup, login (form + JSON), me."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

import db
from auth_utils import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id,
)

router = APIRouter()


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


# ── Signup ────────────────────────────────────────────────────────────────────


@router.post("/signup", status_code=201)
async def signup(body: SignupRequest):
    existing = await db.fetchone(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Username already taken.")

    hashed = hash_password(body.password)
    user_id = await db.execute(
        "INSERT INTO users (username, email, hashed_pw) VALUES (?, ?, ?)",
        (body.username, body.email, hashed),
    )

    token = create_access_token({"sub": str(user_id)})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user_id, "username": body.username},
    }


# ── Login (form — for /docs OAuth2 button) ────────────────────────────────────


@router.post("/token")
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    row = await db.fetchone(
        "SELECT id, username, hashed_pw FROM users WHERE username = ?", (form.username,)
    )
    if not row or not verify_password(form.password, row["hashed_pw"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
        )
    token = create_access_token({"sub": str(row["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": row["id"], "username": row["username"]},
    }


# ── Login (JSON — used by the React frontend) ─────────────────────────────────


@router.post("/login")
async def login_json(body: LoginRequest):
    row = await db.fetchone(
        "SELECT id, username, hashed_pw FROM users WHERE username = ?", (body.username,)
    )
    if not row or not verify_password(body.password, row["hashed_pw"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = create_access_token({"sub": str(row["id"])})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": row["id"], "username": row["username"]},
    }


# ── Me ────────────────────────────────────────────────────────────────────────


@router.get("/me")
async def me(user_id: int = Depends(get_current_user_id)):
    row = await db.fetchone(
        "SELECT id, username, email, created_at FROM users WHERE id = ?", (user_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="User not found.")
    return row
