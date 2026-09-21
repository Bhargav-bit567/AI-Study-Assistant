"""Application configuration loaded from environment variables."""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Azure AI Foundry project endpoint
AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT", "").strip()

# Azure OpenAI Responses API base URL — MUST end with /openai/v1/ or /openai/v1
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()

# Model deployment name
AZURE_MODEL_DEPLOYMENT = os.getenv("AZURE_MODEL_DEPLOYMENT", "gpt-4o-mini").strip()

# Azure API Key
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY", "").strip()

# Agent reference in Azure AI Foundry
AZURE_AI_AGENT_NAME = os.getenv("AZURE_AI_AGENT_NAME", "AI-Study-Assistant").strip()
AZURE_AI_AGENT_VERSION = os.getenv("AZURE_AI_AGENT_VERSION", "2").strip()

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

IS_AZURE_CONFIGURED = bool(AZURE_AI_API_KEY and AZURE_AI_ENDPOINT)
IS_SUPABASE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def validate_config() -> None:
    """Check configuration and log environment status."""
    if IS_AZURE_CONFIGURED:
        logger.info("Azure AI Foundry configured (Agent: %s, Model: %s)",
                    AZURE_AI_AGENT_NAME, AZURE_MODEL_DEPLOYMENT)
    else:
        logger.info(
            "Notice: AZURE_AI_API_KEY is not set in .env. Running with built-in document intelligence engine."
        )

    if IS_SUPABASE_CONFIGURED:
        logger.info("Supabase cloud database configured (%s)", SUPABASE_URL)
    else:
        logger.info(
            "Notice: Supabase credentials not set in .env. Running with local SQLite database for auth and history."
        )
