"""FastAPI backend for AI Study Assistant with Supabase auth + history."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import validate_config, SUPABASE_URL, SUPABASE_ANON_KEY
from .foundry import FoundryClient
from .models import (
    StudyResponse, AuthResponse, SignUpRequest, SignInRequest,
    QuizAttemptRequest, StatsOut,
)
from . import database as db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_config()
    yield


app = FastAPI(title="AI Study Assistant", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Utility ───────────────────────────────────────────────────────────────────

def _get_user_id(authorization: Optional[str]) -> Optional[str]:
    """Extract user_id from Supabase JWT token. Returns None if not authenticated."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1]
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        user = client.auth.get_user(token)
        return user.user.id if user and user.user else None
    except Exception:
        return None


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/api/auth/signup", response_model=AuthResponse)
async def signup(body: SignUpRequest):
    """Register a new user."""
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        res = client.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {"data": {"full_name": body.full_name}},
        })
        if not res.user:
            raise HTTPException(status_code=400, detail="Sign up failed")
        return AuthResponse(
            access_token=res.session.access_token if res.session else "",
            user_id=res.user.id,
            email=res.user.email,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/auth/signin", response_model=AuthResponse)
async def signin(body: SignInRequest):
    """Sign in an existing user."""
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        res = client.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })
        if not res.user or not res.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return AuthResponse(
            access_token=res.session.access_token,
            user_id=res.user.id,
            email=res.user.email,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc))


# ── Study endpoint ────────────────────────────────────────────────────────────

@app.post("/api/study", response_model=StudyResponse)
async def study(
    file: UploadFile = File(...),
    action: Literal["summary", "mcqs"] = Form("summary"),
    authorization: Optional[str] = Header(None),
) -> StudyResponse:
    """Receive a PDF and generate summary or MCQs. Saves results if authenticated."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    user_id = _get_user_id(authorization)

    try:
        client = FoundryClient()
        file_bytes = await file.read()
        file_size = len(file_bytes)

        # Reset file pointer for FoundryClient
        import io
        file.file = io.BytesIO(file_bytes)

        file_id = client.upload_pdf(file)
        result = client.run_study_agent(file_id=file_id, action=action)
    except RuntimeError as exc:
        logger.error("Foundry error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    summary = result.get("summary", "")
    key_points = result.get("key_points", [])
    mcqs = result.get("mcqs", [])

    document_id = None
    result_id = None

    # Save to database if user is authenticated
    if user_id:
        try:
            doc = db.create_document(user_id, file.filename, file_size)
            document_id = doc["id"]
            saved = db.save_result(
                user_id=user_id,
                document_id=document_id,
                action=action,
                summary=summary,
                key_points=key_points,
                mcqs=mcqs,
            )
            result_id = saved["id"]
        except Exception as exc:
            logger.warning("Failed to save result to DB: %s", exc)

    return StudyResponse(
        summary=summary,
        key_points=key_points,
        mcqs=mcqs,
        document_id=document_id,
        result_id=result_id,
    )


# ── History endpoints ─────────────────────────────────────────────────────────

@app.get("/api/history/documents")
async def get_documents(authorization: Optional[str] = Header(None)):
    """Get all documents uploaded by the authenticated user."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return db.get_user_documents(user_id)


@app.get("/api/history/results")
async def get_results(authorization: Optional[str] = Header(None)):
    """Get all generated results for the authenticated user."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return db.get_results(user_id)


@app.get("/api/history/results/{result_id}")
async def get_result(result_id: str, authorization: Optional[str] = Header(None)):
    """Get a single result by ID."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = db.get_result_by_id(result_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result


@app.post("/api/history/quiz")
async def save_quiz(
    body: QuizAttemptRequest,
    authorization: Optional[str] = Header(None),
):
    """Save a quiz attempt with score."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        attempt = db.save_quiz_attempt(
            user_id=user_id,
            result_id=body.result_id,
            score=body.score,
            total=body.total,
            answers=body.answers,
        )
        return attempt
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/history/quiz")
async def get_quiz_attempts(authorization: Optional[str] = Header(None)):
    """Get all quiz attempts for the authenticated user."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return db.get_quiz_attempts(user_id)


@app.get("/api/stats", response_model=StatsOut)
async def get_stats(authorization: Optional[str] = Header(None)):
    """Get dashboard stats for the authenticated user."""
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return db.get_user_stats(user_id)


# ── Serve frontend ────────────────────────────────────────────────────────────
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
