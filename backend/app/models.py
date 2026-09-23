"""Pydantic models for request/response validation."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class MCQ(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list, min_length=4, max_length=4)
    correct_answer: str
    explanation: str


class SummarySection(BaseModel):
    """A titled section of the structured summary."""
    title: str
    content: str


class KeyTerm(BaseModel):
    """A glossary term extracted from the study material."""
    term: str
    definition: str


class StudyResponse(BaseModel):
    # Narrative overview paragraph(s)
    summary: str = ""
    # Titled content sections (the bulk of the detail)
    sections: list[SummarySection] = Field(default_factory=list)
    # Short takeaway bullets
    key_points: list[str] = Field(default_factory=list)
    # Glossary of key terms
    key_terms: list[KeyTerm] = Field(default_factory=list)
    # Exam / revision tips
    study_tips: list[str] = Field(default_factory=list)
    # MCQ data (action=mcqs only)
    mcqs: list[MCQ] = Field(default_factory=list)
    # DB references
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
    sections: list = Field(default_factory=list)
    key_points: list = Field(default_factory=list)
    key_terms: list = Field(default_factory=list)
    study_tips: list = Field(default_factory=list)
    mcqs: list = Field(default_factory=list)
    created_at: str
    documents: Optional[dict] = None


class StatsOut(BaseModel):
    documents_count: int
    results_count: int
    quiz_attempts_count: int
    average_score_pct: int
