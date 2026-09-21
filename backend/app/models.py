"""Pydantic models for request/response validation."""

from typing import Literal

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


class StudyRequestForm:
    """Placeholder for multipart form fields (handled by FastAPI UploadFile)."""

    action: Literal["summary", "mcqs"] = "summary"
