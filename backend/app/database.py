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
    SMTP_LOGIN_NOTIFICATION_ENABLED,
)
from .mail import send_email

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

# Migrate existing databases to add new columns (idempotent)
def _migrate_sqlite():
    with _get_db() as conn:
        for col in ("sections", "key_terms", "study_tips", "overview_blocks"):
            try:
                conn.execute(f"ALTER TABLE results ADD COLUMN {col} TEXT")
                conn.commit()
            except Exception:
                pass  # Column already exists — safe to ignore

_migrate_sqlite()


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

        # Use service role to create the user directly. This bypasses Supabase's
        # email confirmation rate limit, creates a confirmed user immediately,
        # and triggers the profiles table insert automatically.
        sr_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        anon_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

        try:
            res = sr_client.auth.admin.create_user({
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": full_name},
            })
        except Exception as exc:
            err_msg = str(exc)
            logger.warning("Service role create_user error for %s: %s", email, err_msg)
            if any(phrase in err_msg.lower() for phrase in ["already registered", "user already", "already been registered"]):
                raise ValueError("An account with this email already exists.")
            raise ValueError("Sign up failed")

        if not res.user:
            raise ValueError("Sign up failed")

        logger.info(
            "Created user via service role for %s: id=%s, confirmed_at=%s",
            email,
            res.user.id,
            res.user.email_confirmed_at,
        )

        # Sign in the new user to get a session token
        try:
            signin_res = anon_client.auth.sign_in_with_password({
                "email": email,
                "password": password,
            })
            if not signin_res.user or not signin_res.session:
                raise ValueError("Sign up succeeded but could not create session")
            return {
                "access_token": signin_res.session.access_token,
                "user_id": signin_res.user.id,
                "email": signin_res.user.email or email,
                "confirmation_required": False,
            }
        except Exception as exc:
            logger.error("Failed to sign in after service role create for %s: %s", email, exc)
            raise ValueError("Sign up failed")

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
            "confirmation_required": False,
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

        if SMTP_LOGIN_NOTIFICATION_ENABLED:
            send_email(
                to=email,
                subject="Successful login — AI Study Assistant",
                body=(
                    f"Hi there,\n\n"
                    f"We noticed a successful login to your AI Study Assistant account ({email}).\n\n"
                    f"If this wasn't you, please change your password immediately.\n\n"
                    f"— AI Study Assistant"
                ),
            )

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
    overview_blocks: list = None,
    sections: list = None,
    key_points: list = None,
    key_terms: list = None,
    study_tips: list = None,
    mcqs: list = None,
) -> dict:
    overview_blocks = overview_blocks or []
    sections = sections or []
    key_points = key_points or []
    key_terms = key_terms or []
    study_tips = study_tips or []
    mcqs = mcqs or []

    if IS_SUPABASE_CONFIGURED:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

        # Try full schema insert first (new columns).
        try:
            res = client.table("results").insert({
                "user_id": user_id,
                "document_id": document_id,
                "action": action,
                "summary": summary,
                "overview_blocks": overview_blocks,
                "sections": sections,
                "key_points": key_points,
                "key_terms": key_terms,
                "study_tips": study_tips,
                "mcqs": mcqs,
            }).execute()
            return res.data[0]
        except Exception as e:
            err_msg = str(e).lower()
            # If the new columns don't exist yet, fall back to the original schema.
            if "overview_blocks" in err_msg or "sections" in err_msg or "key_terms" in err_msg or "study_tips" in err_msg:
                logger.warning("Supabase results table missing new columns; falling back to original schema insert: %s", e)
                try:
                    res = client.table("results").insert({
                        "user_id": user_id,
                        "document_id": document_id,
                        "action": action,
                        "summary": summary,
                        "key_points": key_points,
                        "mcqs": mcqs,
                    }).execute()
                    return res.data[0]
                except Exception as e2:
                    logger.warning("Supabase original-schema save_result failed, using local DB: %s", e2)
            else:
                logger.warning("Supabase save_result failed, using local DB: %s", e)

    with _get_db() as conn:
        res_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO results
               (id, document_id, user_id, action, summary, overview_blocks, sections, key_points, key_terms, study_tips, mcqs, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                res_id,
                document_id,
                user_id,
                action,
                summary,
                json.dumps(overview_blocks),
                json.dumps(sections),
                json.dumps(key_points),
                json.dumps(key_terms),
                json.dumps(study_tips),
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
            "overview_blocks": overview_blocks,
            "sections": sections,
            "key_points": key_points,
            "key_terms": key_terms,
            "study_tips": study_tips,
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
            for field in ("key_points", "mcqs", "sections", "key_terms", "study_tips", "overview_blocks"):
                try:
                    r[field] = json.loads(r[field]) if r.get(field) else []
                except Exception:
                    r[field] = []
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
        for field in ("key_points", "mcqs", "sections", "key_terms", "study_tips", "overview_blocks"):
            try:
                r[field] = json.loads(r[field]) if r.get(field) else []
            except Exception:
                r[field] = []
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
