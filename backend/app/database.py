"""Database layer supporting both Supabase and built-in SQLite persistence."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import uuid
import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

import jwt
from .config import (
    SUPABASE_URL,
    SUPABASE_ANON_KEY,
    SUPABASE_SERVICE_ROLE_KEY,
    IS_SUPABASE_CONFIGURED,
)

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).resolve().parent / "study_assistant.db"
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ai-study-assistant-local-secret-key-2026")


# ── SQLite Setup for local mode ────────────────────────────────────────────────

def _get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _init_sqlite():
    with _get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS results (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                summary TEXT,
                key_points TEXT,
                mcqs TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS quiz_attempts (
                id TEXT PRIMARY KEY,
                result_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                answers TEXT,
                attempted_at TEXT NOT NULL,
                FOREIGN KEY (result_id) REFERENCES results(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
        """)


_init_sqlite()


def _hash_password(password: str) -> str:
    salt = "ai_study_salt_"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc).timestamp() + 86400 * 30,  # 30 days
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(token: str) -> Optional[str]:
    """Verify either a Supabase JWT or a local JWT token and return the user_id."""
    if not token:
        return None

    # Try local JWT first
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("sub")
    except Exception:
        pass

    # Try Supabase token if configured
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            user = client.auth.get_user(token)
            return user.user.id if user and user.user else None
        except Exception:
            pass

    return None


# ── Auth Operations ───────────────────────────────────────────────────────────

def sign_up(email: str, password: str, full_name: str = "") -> dict:
    email = email.strip().lower()
    if IS_SUPABASE_CONFIGURED:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        res = client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"full_name": full_name}},
        })
        if not res.user:
            raise ValueError("Sign up failed")
        token = res.session.access_token if res.session else ""
        return {
            "access_token": token,
            "user_id": res.user.id,
            "email": res.user.email or email,
        }

    # Local SQLite fallback
    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            raise ValueError("An account with this email already exists.")

        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        pwd_hash = _hash_password(password)

        cursor.execute(
            "INSERT INTO users (id, email, password_hash, full_name, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, pwd_hash, full_name, created_at),
        )
        conn.commit()

        token = create_token(user_id, email)
        return {
            "access_token": token,
            "user_id": user_id,
            "email": email,
        }


def sign_in(email: str, password: str) -> dict:
    email = email.strip().lower()
    if IS_SUPABASE_CONFIGURED:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
        res = client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        if not res.user or not res.session:
            raise ValueError("Invalid credentials")
        return {
            "access_token": res.session.access_token,
            "user_id": res.user.id,
            "email": res.user.email or email,
        }

    # Local SQLite fallback
    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if not row or row["password_hash"] != _hash_password(password):
            raise ValueError("Invalid email or password.")

        token = create_token(row["id"], row["email"])
        return {
            "access_token": token,
            "user_id": row["id"],
            "email": row["email"],
        }


# ── Document Helpers ──────────────────────────────────────────────────────────

def create_document(user_id: str, filename: str, file_size: int) -> dict:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = client.table("documents").insert({
                "user_id": user_id,
                "filename": filename,
                "file_size": file_size,
            }).execute()
            return res.data[0]
        except Exception as e:
            logger.warning("Supabase create_document failed, using local DB: %s", e)

    with _get_db() as conn:
        doc_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO documents (id, user_id, filename, file_size, created_at) VALUES (?, ?, ?, ?, ?)",
            (doc_id, user_id, filename, file_size, created_at),
        )
        conn.commit()
        return {"id": doc_id, "user_id": user_id, "filename": filename, "file_size": file_size, "created_at": created_at}


def get_user_documents(user_id: str) -> list:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = (
                client.table("documents")
                .select("*, results(id, action, created_at)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return res.data
        except Exception as e:
            logger.warning("Supabase get_user_documents failed, using local DB: %s", e)

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        )
        docs = [dict(row) for row in cursor.fetchall()]
        for doc in docs:
            cursor.execute(
                "SELECT id, action, created_at FROM results WHERE document_id = ? ORDER BY created_at DESC",
                (doc["id"],),
            )
            doc["results"] = [dict(r) for r in cursor.fetchall()]
        return docs


# ── Result Helpers ────────────────────────────────────────────────────────────

def save_result(
    user_id: str,
    document_id: str,
    action: str,
    summary: str = "",
    key_points: list = None,
    mcqs: list = None,
) -> dict:
    key_points = key_points or []
    mcqs = mcqs or []

    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = client.table("results").insert({
                "user_id": user_id,
                "document_id": document_id,
                "action": action,
                "summary": summary,
                "key_points": key_points,
                "mcqs": mcqs,
            }).execute()
            return res.data[0]
        except Exception as e:
            logger.warning("Supabase save_result failed, using local DB: %s", e)

    with _get_db() as conn:
        res_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO results (id, document_id, user_id, action, summary, key_points, mcqs, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                res_id,
                document_id,
                user_id,
                action,
                summary,
                json.dumps(key_points),
                json.dumps(mcqs),
                created_at,
            ),
        )
        conn.commit()
        return {
            "id": res_id,
            "document_id": document_id,
            "user_id": user_id,
            "action": action,
            "summary": summary,
            "key_points": key_points,
            "mcqs": mcqs,
            "created_at": created_at,
        }


def get_results(user_id: str) -> list:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = (
                client.table("results")
                .select("*, documents(filename, file_size)")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .execute()
            )
            return res.data
        except Exception as e:
            logger.warning("Supabase get_results failed, using local DB: %s", e)

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT r.*, d.filename, d.file_size
               FROM results r
               LEFT JOIN documents d ON r.document_id = d.id
               WHERE r.user_id = ?
               ORDER BY r.created_at DESC""",
            (user_id,),
        )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            r = dict(row)
            try:
                r["key_points"] = json.loads(r["key_points"]) if r["key_points"] else []
            except Exception:
                r["key_points"] = []
            try:
                r["mcqs"] = json.loads(r["mcqs"]) if r["mcqs"] else []
            except Exception:
                r["mcqs"] = []
            r["documents"] = {"filename": r.pop("filename", "Unknown file"), "file_size": r.pop("file_size", 0)}
            results.append(r)
        return results


def get_result_by_id(result_id: str, user_id: str) -> Optional[dict]:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = (
                client.table("results")
                .select("*, documents(filename)")
                .eq("id", result_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return res.data
        except Exception as e:
            logger.warning("Supabase get_result_by_id failed, using local DB: %s", e)

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT r.*, d.filename
               FROM results r
               LEFT JOIN documents d ON r.document_id = d.id
               WHERE r.id = ? AND r.user_id = ?""",
            (result_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            return None
        r = dict(row)
        try:
            r["key_points"] = json.loads(r["key_points"]) if r["key_points"] else []
        except Exception:
            r["key_points"] = []
        try:
            r["mcqs"] = json.loads(r["mcqs"]) if r["mcqs"] else []
        except Exception:
            r["mcqs"] = []
        r["documents"] = {"filename": r.pop("filename", "Unknown file")}
        return r


# ── Quiz Attempt Helpers ──────────────────────────────────────────────────────

def save_quiz_attempt(
    user_id: str,
    result_id: str,
    score: int,
    total: int,
    answers: list,
) -> dict:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = client.table("quiz_attempts").insert({
                "user_id": user_id,
                "result_id": result_id,
                "score": score,
                "total": total,
                "answers": answers,
            }).execute()
            return res.data[0]
        except Exception as e:
            logger.warning("Supabase save_quiz_attempt failed, using local DB: %s", e)

    with _get_db() as conn:
        attempt_id = str(uuid.uuid4())
        attempted_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO quiz_attempts (id, result_id, user_id, score, total, answers, attempted_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                attempt_id,
                result_id,
                user_id,
                score,
                total,
                json.dumps(answers),
                attempted_at,
            ),
        )
        conn.commit()
        return {
            "id": attempt_id,
            "result_id": result_id,
            "user_id": user_id,
            "score": score,
            "total": total,
            "answers": answers,
            "attempted_at": attempted_at,
        }


def get_quiz_attempts(user_id: str) -> list:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
            res = (
                client.table("quiz_attempts")
                .select("*, results(action, documents(filename))")
                .eq("user_id", user_id)
                .order("attempted_at", desc=True)
                .execute()
            )
            return res.data
        except Exception as e:
            logger.warning("Supabase get_quiz_attempts failed, using local DB: %s", e)

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT q.*, r.action, d.filename
               FROM quiz_attempts q
               LEFT JOIN results r ON q.result_id = r.id
               LEFT JOIN documents d ON r.document_id = d.id
               WHERE q.user_id = ?
               ORDER BY q.attempted_at DESC""",
            (user_id,),
        )
        rows = cursor.fetchall()
        attempts = []
        for row in rows:
            q = dict(row)
            try:
                q["answers"] = json.loads(q["answers"]) if q["answers"] else []
            except Exception:
                q["answers"] = []
            filename = q.pop("filename", "Unknown file")
            action = q.pop("action", "mcqs")
            q["results"] = {"action": action, "documents": {"filename": filename}}
            attempts.append(q)
        return attempts


# ── User Stats Helper ─────────────────────────────────────────────────────────

def get_user_stats(user_id: str) -> dict:
    if IS_SUPABASE_CONFIGURED:
        try:
            from supabase import create_client
            client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
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
        except Exception as e:
            logger.warning("Supabase get_user_stats failed, using local DB: %s", e)

    with _get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?", (user_id,))
        docs_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT COUNT(*) as cnt FROM results WHERE user_id = ?", (user_id,))
        results_count = cursor.fetchone()["cnt"]

        cursor.execute("SELECT score, total FROM quiz_attempts WHERE user_id = ?", (user_id,))
        attempts = cursor.fetchall()

        total_score = sum(a["score"] for a in attempts)
        total_possible = sum(a["total"] for a in attempts)
        avg_score = round((total_score / total_possible) * 100) if total_possible else 0

        return {
            "documents_count": docs_count,
            "results_count": results_count,
            "quiz_attempts_count": len(attempts),
            "average_score_pct": avg_score,
        }
