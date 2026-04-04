"""Model tier detection from environment and config files."""

from __future__ import annotations

import os
from pathlib import Path


def _detect_model_tier(project_path: Path) -> str | None:
    """Detect preferred model tier from environment/config files."""

    # Check environment variables
    env_vars = [
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_KEY",
        "GOOGLE_API_KEY", "COHERE_API_KEY"
    ]

    for var in env_vars:
        if os.environ.get(var):
            # If premium API keys present, suggest balanced or premium
            if "ANTHROPIC" in var:
                return "balanced"  # Claude is good middle ground
            return "cheap"  # OpenAI cheap tier for cost-effective

    # Check .env files
    env_files = [".env", ".env.local", ".env.development"]
    for env_file in env_files:
        env_path = project_path / env_file
        if env_path.exists():
            try:
                content = env_path.read_text(encoding="utf-8")
                if "ANTHROPIC" in content or "CLAUDE" in content:
                    return "balanced"
                if "OPENAI" in content or "GPT" in content:
                    return "cheap"
            except Exception:
                pass

    # Check config files
    config_files = [
        project_path / "config.yaml",
        project_path / "config.yml",
        project_path / ".planfile" / "config.yaml",
    ]

    for config_path in config_files:
        if config_path.exists():
            try:
                content = config_path.read_text(encoding="utf-8")
                if "claude" in content.lower() or "opus" in content.lower():
                    return "premium"
                if "gpt-4" in content.lower():
                    return "balanced"
                if "local" in content.lower() or "ollama" in content.lower():
                    return "free"
            except Exception:
                pass

    return None
