"""Azure AI Foundry integration — matches the pattern shown in the Foundry portal."""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from .config import (
    AZURE_AI_AGENT_NAME,
    AZURE_AI_AGENT_VERSION,
    AZURE_AI_API_KEY,
    AZURE_MODEL_DEPLOYMENT,
    AZURE_OPENAI_ENDPOINT,
)

if TYPE_CHECKING:
    from fastapi import UploadFile

logger = logging.getLogger(__name__)


class FoundryClient:
    """Calls the Responses API exactly as shown in the Foundry portal snippet:

        endpoint = "https://ai-study-assistant-resource.services.ai.azure.com/..."
        deployment_name = "gpt-5-mini"
        client = OpenAI(base_url=endpoint, api_key=...)
        response = client.responses.create(model=deployment_name, ...)
    """

    def __init__(self) -> None:
        if not AZURE_AI_API_KEY:
            raise RuntimeError("AZURE_AI_API_KEY is not set in .env")

        logger.info("FoundryClient ready — endpoint: %s  model: %s",
                    AZURE_OPENAI_ENDPOINT, AZURE_MODEL_DEPLOYMENT)

        # The project endpoint requires "api-key" header, not "Authorization: Bearer".
        # Pass it as a default header since OpenAI() uses Bearer by default.
        self.client = OpenAI(
            base_url=AZURE_OPENAI_ENDPOINT,
            api_key="placeholder",  # required by SDK but overridden below
            default_headers={"api-key": AZURE_AI_API_KEY},
        )

    def upload_pdf(self, upload_file: UploadFile) -> str:
        """Read PDF bytes, base64-encode, return as JSON payload (no network call)."""
        filename = upload_file.filename or "notes.pdf"
        raw_bytes = upload_file.file.read()
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        logger.info("Encoded %s (%d bytes) as base64", filename, len(raw_bytes))
        return json.dumps({
            "filename": filename,
            "data_uri": f"data:application/pdf;base64,{b64}",
        })

    def delete_file(self, file_id: str) -> None:
        """No-op — inline base64 needs no cleanup."""
        pass

    def run_study_agent(self, file_id: str, action: str) -> dict:
        """Call the Responses API with the PDF inline and the agent reference."""
        file_info = json.loads(file_id)
        prompt = self._build_prompt(action)

        try:
            response = self.client.responses.create(
                model=AZURE_MODEL_DEPLOYMENT,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_file",
                                "filename": file_info["filename"],
                                "file_data": file_info["data_uri"],
                            },
                            {"type": "input_text", "text": prompt},
                        ],
                    }
                ],
                extra_body={
                    "agent_reference": {
                        "name": AZURE_AI_AGENT_NAME,
                        "version": AZURE_AI_AGENT_VERSION,
                        "type": "agent_reference",
                    },
                },
                timeout=120,
            )

            logger.info("Response received for action=%s", action)
            output_text = getattr(response, "output_text", None)
            if not output_text and hasattr(response, "choices") and response.choices:
                output_text = response.choices[0].message.content
            if not output_text:
                output_text = str(response)

            return self._extract_json(output_text)

        except Exception as exc:
            logger.error("Agent call failed: %s", exc)
            raise RuntimeError(f"Azure Agent Invocation Failed: {exc}") from exc

    def _build_prompt(self, action: str) -> str:
        if action == "summary":
            return (
                "Read the attached study material and return ONLY a JSON object "
                "with no markdown and no extra text:\n"
                '{"summary": "...", "key_points": ["...", "..."]}\n\n'
                "The summary should be concise. Key points should be short bullets."
            )
        if action == "mcqs":
            return (
                "Read the attached study material and return ONLY a JSON object "
                "with no markdown and no extra text:\n"
                '{"mcqs": [{"question": "...", "options": ["...", "...", "...", "..."], '
                '"correct_answer": "...", "explanation": "..."}]}\n\n'
                "Generate 5 multiple-choice questions with 4 options each. "
                "Mix easy, medium, and hard difficulty."
            )
        raise ValueError(f"Unsupported action: {action}")

    def _extract_json(self, text: str) -> dict:
        """Extract the JSON payload from the agent's response text."""
        text = text.strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()

        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1]

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            logger.error("Could not parse JSON from response: %s", text[:500])
            raise RuntimeError(f"Agent did not return valid JSON: {text[:200]}") from exc
