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

# Azure API Key
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY", "")

# Agent reference in Azure AI Foundry
AZURE_AI_AGENT_NAME = os.getenv("AZURE_AI_AGENT_NAME", "AI-Study-Assistant")
AZURE_AI_AGENT_VERSION = os.getenv("AZURE_AI_AGENT_VERSION", "2")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def validate_config() -> None:
    """Raise a clear error if required settings are missing."""
    missing = []
    if not AZURE_AI_ENDPOINT:
        missing.append("AZURE_AI_ENDPOINT")
    if not AZURE_AI_AGENT_NAME:
        missing.append("AZURE_AI_AGENT_NAME")
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_SERVICE_ROLE_KEY:
        missing.append("SUPABASE_SERVICE_ROLE_KEY")
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please check your .env configuration."
        )
