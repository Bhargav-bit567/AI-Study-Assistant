"""Supabase database client and helper functions."""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


def get_admin_client() -> Client:
    """Service-role client — bypasses RLS. Use only for server-side ops."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def get_anon_client() -> Client:
    """Anon client — respects RLS. Used for auth operations."""
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ── Document helpers ──────────────────────────────────────────────────────────

def create_document(user_id: str, filename: str, file_size: int) -> dict:
    """Insert a document record and return it."""
    client = get_admin_client()
    res = client.table("documents").insert({
        "user_id": user_id,
        "filename": filename,
        "file_size": file_size,
    }).execute()
    return res.data[0]


def get_user_documents(user_id: str) -> list:
    """Return all documents for a user, newest first."""
    client = get_admin_client()
    res = (
        client.table("documents")
        .select("*, results(id, action, created_at)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


# ── Result helpers ────────────────────────────────────────────────────────────

def save_result(
    user_id: str,
    document_id: str,
    action: str,
    summary: str = "",
    key_points: list = None,
    mcqs: list = None,
) -> dict:
    """Save a generated summary or MCQ result."""
    client = get_admin_client()
    res = client.table("results").insert({
        "user_id": user_id,
        "document_id": document_id,
        "action": action,
        "summary": summary,
        "key_points": key_points or [],
        "mcqs": mcqs or [],
    }).execute()
    return res.data[0]


def get_results(user_id: str) -> list:
    """Return all results for a user with document info, newest first."""
    client = get_admin_client()
    res = (
        client.table("results")
        .select("*, documents(filename, file_size)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data


def get_result_by_id(result_id: str, user_id: str) -> Optional[dict]:
    """Return a single result by ID, scoped to the user."""
    client = get_admin_client()
    res = (
        client.table("results")
        .select("*, documents(filename)")
        .eq("id", result_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    return res.data


# ── Quiz attempt helpers ──────────────────────────────────────────────────────

def save_quiz_attempt(
    user_id: str,
    result_id: str,
    score: int,
    total: int,
    answers: list,
) -> dict:
    """Save a quiz attempt with score and answers."""
    client = get_admin_client()
    res = client.table("quiz_attempts").insert({
        "user_id": user_id,
        "result_id": result_id,
        "score": score,
        "total": total,
        "answers": answers,
    }).execute()
    return res.data[0]


def get_quiz_attempts(user_id: str) -> list:
    """Return all quiz attempts for a user, newest first."""
    client = get_admin_client()
    res = (
        client.table("quiz_attempts")
        .select("*, results(action, documents(filename))")
        .eq("user_id", user_id)
        .order("attempted_at", desc=True)
        .execute()
    )
    return res.data


# ── User helpers ──────────────────────────────────────────────────────────────

def get_user_stats(user_id: str) -> dict:
    """Return summary stats for a user's dashboard."""
    client = get_admin_client()

    docs = client.table("documents").select("id", count="exact").eq("user_id", user_id).execute()
    results = client.table("results").select("id", count="exact").eq("user_id", user_id).execute()
    attempts = client.table("quiz_attempts").select("score, total").eq("user_id", user_id).execute()

    total_score = sum(a["score"] for a in attempts.data)
    total_possible = sum(a["total"] for a in attempts.data)
    avg_score = round((total_score / total_possible) * 100) if total_possible else 0

    return {
        "documents_count": docs.count or 0,
        "results_count": results.count or 0,
        "quiz_attempts_count": len(attempts.data),
        "average_score_pct": avg_score,
    }
