"""Pydantic models for request/response validation."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class MCQ(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list, min_length=4, max_length=4)
    correct_answer: str
    explanation: str


class StudyResponse(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    mcqs: list[MCQ] = Field(default_factory=list)
    document_id: Optional[str] = None
    result_id: Optional[str] = None


# ── Auth models ───────────────────────────────────────────────────────────────

class SignUpRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = ""


class SignInRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    user_id: str
    email: str
    confirmation_required: bool = False


# ── Quiz attempt model ────────────────────────────────────────────────────────

class QuizAttemptRequest(BaseModel):
    result_id: str
    score: int
    total: int
    answers: list[dict] = Field(default_factory=list)


# ── History models ────────────────────────────────────────────────────────────

class DocumentOut(BaseModel):
    id: str
    filename: str
    file_size: Optional[int]
    created_at: str
    results: list = Field(default_factory=list)


class ResultOut(BaseModel):
    id: str
    action: str
    summary: str = ""
    key_points: list = Field(default_factory=list)
    mcqs: list = Field(default_factory=list)
    created_at: str
    documents: Optional[dict] = None


class StatsOut(BaseModel):
    documents_count: int
    results_count: int
    quiz_attempts_count: int
    average_score_pct: int
