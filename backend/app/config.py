"""Application configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()

# Azure AI Foundry project endpoint
AZURE_AI_ENDPOINT = os.getenv(
    "AZURE_AI_ENDPOINT",
    "https://ai-study-assistant-resource.services.ai.azure.com/api/projects/ai-study-assistant",
)

# Azure OpenAI Responses API base URL — MUST end with /openai/v1/
AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT",
    "https://ai-study-assistant-resource.services.ai.azure.com/api/projects/ai-study-assistant/openai/v1/",
)

# Model deployment name
AZURE_MODEL_DEPLOYMENT = os.getenv("AZURE_MODEL_DEPLOYMENT", "gpt-5-mini")

# Optional API Key (for API key authentication)
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY", "")

# Agent reference in Azure AI Foundry
AZURE_AI_AGENT_NAME = os.getenv("AZURE_AI_AGENT_NAME", "AI-Study-Assistant")
AZURE_AI_AGENT_VERSION = os.getenv("AZURE_AI_AGENT_VERSION", "2")


def validate_config() -> None:
    """Raise a clear error if required Azure settings are missing."""
    missing = []
    if not AZURE_AI_ENDPOINT:
        missing.append("AZURE_AI_ENDPOINT")
    if not AZURE_AI_AGENT_NAME:
        missing.append("AZURE_AI_AGENT_NAME")
    if not AZURE_AI_AGENT_VERSION:
        missing.append("AZURE_AI_AGENT_VERSION")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please check your .env configuration."
        )
