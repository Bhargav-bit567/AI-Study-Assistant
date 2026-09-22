"""Unit, integration and contract tests for the AI Study Assistant backend."""

import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app

TEST_PDF_PATH = Path(__file__).resolve().parent.parent.parent / "test_notes.pdf"


class TestStudyAssistantAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        """Verify that the /health endpoint returns status ok."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")

    def test_study_rejects_non_pdf(self):
        """Verify that uploading a non-PDF file returns 400 Bad Request."""
        response = self.client.post(
            "/api/study",
            files={"file": ("test.txt", b"plain text", "text/plain")},
            data={"action": "summary"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only PDF files are supported", response.json()["detail"])

    def test_study_summary_flow_real_pdf(self):
        """Verify that /api/study generates a structured summary from the real PDF."""
        with open(TEST_PDF_PATH, "rb") as f:
            pdf_bytes = f.read()

        response = self.client.post(
            "/api/study",
            files={"file": ("test_notes.pdf", pdf_bytes, "application/pdf")},
            data={"action": "summary"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(len(data["summary"]) > 0)
        self.assertTrue(len(data["key_points"]) > 0)

    def test_study_mcqs_flow_real_pdf(self):
        """Verify that /api/study generates valid MCQs with 4 options from the real PDF."""
        with open(TEST_PDF_PATH, "rb") as f:
            pdf_bytes = f.read()

        response = self.client.post(
            "/api/study",
            files={"file": ("test_notes.pdf", pdf_bytes, "application/pdf")},
            data={"action": "mcqs"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["mcqs"]), 5)
        for mcq in data["mcqs"]:
            self.assertTrue(len(mcq["question"]) > 0)
            self.assertEqual(len(mcq["options"]), 4)
            self.assertIn(mcq["correct_answer"], mcq["options"])
            self.assertTrue(len(mcq["explanation"]) > 0)

    def test_auth_and_history_lifecycle(self):
        """Verify user signup, signin, authenticated study save, and quiz stats."""
        import uuid
        from supabase import create_client
        from backend.app.config import SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

        test_email = f"student_test_{uuid.uuid4().hex[:8]}@example.com"
        test_pwd = "password123"

        # 1. Create a pre-confirmed test user via service role
        admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
        created = admin_client.auth.admin.create_user({
            "email": test_email,
            "password": test_pwd,
            "email_confirm": True,
            "user_metadata": {"full_name": "Test Student"},
        })
        self.assertIsNotNone(created.user)

        # 2. Sign in
        res_signin = self.client.post(
            "/api/auth/signin",
            json={"email": test_email, "password": test_pwd},
        )
        self.assertEqual(res_signin.status_code, 200)
        auth_data = res_signin.json()
        self.assertFalse(auth_data["confirmation_required"])
        token = auth_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 3. Authenticated study request
        with open(TEST_PDF_PATH, "rb") as f:
            pdf_bytes = f.read()

        res_study = self.client.post(
            "/api/study",
            files={"file": ("test_notes.pdf", pdf_bytes, "application/pdf")},
            data={"action": "mcqs"},
            headers=headers,
        )
        self.assertEqual(res_study.status_code, 200)
        study_data = res_study.json()
        self.assertIsNotNone(study_data["document_id"])
        self.assertIsNotNone(study_data["result_id"])

        # 4. Save quiz attempt
        res_quiz = self.client.post(
            "/api/history/quiz",
            json={
                "result_id": study_data["result_id"],
                "score": 4,
                "total": 5,
                "answers": [{"question": "Q1", "selected": "A", "correct": "A", "is_correct": True}],
            },
            headers=headers,
        )
        self.assertEqual(res_quiz.status_code, 200)

        # 5. Check dashboard stats
        res_stats = self.client.get("/api/stats", headers=headers)
        self.assertEqual(res_stats.status_code, 200)
        stats = res_stats.json()
        self.assertGreaterEqual(stats["documents_count"], 1)
        self.assertGreaterEqual(stats["results_count"], 1)
        self.assertGreaterEqual(stats["quiz_attempts_count"], 1)
        self.assertEqual(stats["average_score_pct"], 80)

        # Clean up test user
        admin_client.auth.admin.delete_user(created.user.id)


if __name__ == "__main__":
    unittest.main()
