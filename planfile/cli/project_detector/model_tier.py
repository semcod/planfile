"""Model tier detection from environment and config files."""

from __future__ import annotations

import os
from pathlib import Path


_ENV_VARS = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AZURE_OPENAI_KEY", "GOOGLE_API_KEY", "COHERE_API_KEY"]
_ENV_FILES = [".env", ".env.local", ".env.development"]
_CONFIG_FILES = ["config.yaml", "config.yml", ".planfile/config.yaml"]


def _tier_from_env_vars() -> str | None:
    """Detect tier from environment variable API keys."""
    for var in _ENV_VARS:
        if os.environ.get(var):
            return "balanced" if "ANTHROPIC" in var else "cheap"
    return None


def _tier_from_env_files(project_path: Path) -> str | None:
    """Detect tier from .env files in the project."""
    for env_file in _ENV_FILES:
        env_path = project_path / env_file
        if not env_path.exists():
            continue
        try:
            content = env_path.read_text(encoding="utf-8")
            if "ANTHROPIC" in content or "CLAUDE" in content:
                return "balanced"
            if "OPENAI" in content or "GPT" in content:
                return "cheap"
        except Exception:
            pass
    return None


def _tier_from_config_files(project_path: Path) -> str | None:
    """Detect tier from config files in the project."""
    for rel_path in _CONFIG_FILES:
        config_path = project_path / rel_path
        if not config_path.exists():
            continue
        try:
            content = config_path.read_text(encoding="utf-8").lower()
            if "claude" in content or "opus" in content:
                return "premium"
            if "gpt-4" in content:
                return "balanced"
            if "local" in content or "ollama" in content:
                return "free"
        except Exception:
            pass
    return None


def _detect_model_tier(project_path: Path) -> str | None:
    """Detect preferred model tier from environment/config files."""
    return _tier_from_env_vars() or _tier_from_env_files(project_path) or _tier_from_config_files(project_path)
