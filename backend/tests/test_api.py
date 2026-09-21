"""Unit and contract tests for the AI Study Assistant backend."""

import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.app.main import app


class TestStudyAssistantAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        """Verify that the /health endpoint returns status ok."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_study_rejects_non_pdf(self):
        """Verify that uploading a non-PDF file returns 400 Bad Request."""
        response = self.client.post(
            "/api/study",
            files={"file": ("test.txt", b"plain text", "text/plain")},
            data={"action": "summary"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only PDF files are supported", response.json()["detail"])

    def test_study_summary_flow_mocked(self):
        """Verify that /api/study handles summary responses correctly with mocked Foundry."""
        mock_result = {
            "summary": "This is a computer networks summary.",
            "key_points": ["Point A", "Point B"],
            "mcqs": [],
        }

        with patch("backend.app.main.FoundryClient") as MockFoundry:
            instance = MockFoundry.return_value
            instance.upload_pdf.return_value = "file-12345"
            instance.run_study_agent.return_value = mock_result

            response = self.client.post(
                "/api/study",
                files={"file": ("test.pdf", b"%PDF-1.4 dummy content", "application/pdf")},
                data={"action": "summary"},
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["summary"], "This is a computer networks summary.")
            self.assertEqual(len(data["key_points"]), 2)
            self.assertTrue(instance.upload_pdf.called)

    def test_study_mcqs_flow_mocked(self):
        """Verify that /api/study handles MCQ responses correctly with mocked Foundry."""
        mock_result = {
            "summary": "",
            "key_points": [],
            "mcqs": [
                {
                    "question": "What does IP stand for?",
                    "options": [
                        "Internet Protocol",
                        "Internal Process",
                        "Input Port",
                        "Interlink Provider",
                    ],
                    "correct_answer": "Internet Protocol",
                    "explanation": "IP stands for Internet Protocol in networking.",
                }
            ],
        }

        with patch("backend.app.main.FoundryClient") as MockFoundry:
            instance = MockFoundry.return_value
            instance.upload_pdf.return_value = "file-12345"
            instance.run_study_agent.return_value = mock_result

            response = self.client.post(
                "/api/study",
                files={"file": ("test.pdf", b"%PDF-1.4 dummy content", "application/pdf")},
                data={"action": "mcqs"},
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data["mcqs"]), 1)
            self.assertEqual(data["mcqs"][0]["question"], "What does IP stand for?")
            self.assertEqual(data["mcqs"][0]["correct_answer"], "Internet Protocol")


if __name__ == "__main__":
    unittest.main()
