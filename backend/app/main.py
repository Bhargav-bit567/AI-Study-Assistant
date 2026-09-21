"""FastAPI backend for AI Study Assistant."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import validate_config
from .foundry import FoundryClient
from .models import StudyResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate config on startup."""
    validate_config()
    yield


app = FastAPI(
    title="AI Study Assistant Backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/api/study", response_model=StudyResponse)
async def study(
    file: UploadFile = File(...),
    action: Literal["summary", "mcqs"] = Form("summary"),
) -> StudyResponse:
    """Receive a PDF and request a summary or MCQs from the AI agent."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not file.content_type or "pdf" not in file.content_type.lower():
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        client = FoundryClient()
        file_id = client.upload_pdf(file)
        result = client.run_study_agent(file_id=file_id, action=action)
    except RuntimeError as exc:
        logger.error("Foundry error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500, detail="Internal server error processing your request"
        ) from exc

    summary = result.get("summary", "")
    key_points = result.get("key_points", [])
    mcqs = result.get("mcqs", [])

    return StudyResponse(summary=summary, key_points=key_points, mcqs=mcqs)


# Mount frontend static files if directory exists
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
