"""Configuration management for integrations with support for multiple config files."""

import os
import re
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


class IntegrationConfig:
    """Manages integration configuration with support for multiple config files."""

    def __init__(self, directory: str = "."):
        self.directory = Path(directory)
        self.config = {}
        self.load_dotenv()

    def load_dotenv(self):
        """Load .env file if it exists."""
        env_file = self.directory / ".env"
        if env_file.exists():
            load_dotenv(env_file)

    def _expand_env_vars(self, config: Any) -> Any:
        """Recursively expand environment variables in configuration."""
        if isinstance(config, dict):
            return {k: self._expand_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._expand_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Expand ${VAR_NAME} and $VAR_NAME patterns
            def replace_env_var(match):
                var_name = match.group(1) if match.group(1) else match.group(2)
                return os.environ.get(var_name, match.group(0))

            # Match both ${VAR} and $VAR patterns
            pattern = r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)'
            return re.sub(pattern, replace_env_var, config)
        else:
            return config

    def discover_configs(self) -> list[Path]:
        """Discover all *.planfile.yaml files in the directory and .planfile/ subdir."""
        configs = []
        for pattern in ["*.planfile.yaml", "*.planfile.yml"]:
            configs.extend(self.directory.glob(pattern))
            # Also search in .planfile/ subdirectory
            configs.extend((self.directory / ".planfile").glob(pattern))
        return sorted(set(configs))

    def load_configs(self) -> dict[str, Any]:
        """Load and merge all configuration files."""
        self.config = {}

        # Load integration configs first (e.g., github.planfile.yaml)
        for config_file in self.discover_configs():
            if config_file.name.startswith("tickets."):
                continue  # Skip ticket files for now

            with open(config_file) as f:
                file_config = yaml.safe_load(f) or {}
                # Expand environment variables in the loaded config
                file_config = self._expand_env_vars(file_config)
                self._deep_merge(self.config, file_config)

        # Load ticket configs last
        for config_file in self.discover_configs():
            if config_file.name.startswith("tickets."):
                with open(config_file) as f:
                    file_config = yaml.safe_load(f) or {}
                    # Expand environment variables in the loaded config
                    file_config = self._expand_env_vars(file_config)
                    self._deep_merge(self.config, file_config)

        return self.config

    def get_integration_config(self, integration_name: str) -> dict[str, Any]:
        """Get configuration for a specific integration."""
        if not self.config:
            self.load_configs()

        return self.config.get("integrations", {}).get(integration_name, {})

    def get_project_config(self) -> dict[str, Any]:
        """Get project configuration."""
        if not self.config:
            self.load_configs()

        return self.config.get("project", {})

    def get_sprint_config(self) -> dict[str, Any]:
        """Get sprint configuration."""
        if not self.config:
            self.load_configs()

        return self.config.get("sprint", {})

    def get_backlog_config(self) -> dict[str, Any]:
        """Get backlog configuration."""
        if not self.config:
            self.load_configs()

        return self.config.get("backlog", {})

    def _deep_merge(self, base: dict, update: dict):
        """Deep merge two dictionaries."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def validate_integration(self, integration_name: str) -> bool:
        """Validate that an integration has required configuration."""
        config = self.get_integration_config(integration_name)

        if not config:
            # Markdown integration is always valid as it has defaults
            if integration_name == "markdown":
                return True
            return False

        # Check for required fields based on integration type
        if integration_name == "github":
            return "repo" in config
        elif integration_name == "gitlab":
            return "url" in config and "project_id" in config
        elif integration_name == "jira":
            return "url" in config and "project" in config
        elif integration_name == "markdown":
            # Markdown integration is always valid with defaults
            return True

        return True

    def has_configured_integrations(self) -> bool:
        """Check if any valid integrations are configured."""
        if not self.config:
            self.load_configs()

        integrations = self.config.get("integrations", {})

        # Check for any non-empty integration config
        for name, config in integrations.items():
            if config and isinstance(config, dict):
                # Skip if it's just the markdown default
                if name == "markdown" and config.get("is_default", False):
                    continue
                if any(v for v in config.values() if v is not None):
                    return True

        return False

    def get_default_backend(self):
        """Get the default markdown backend when no integrations are configured."""
        from planfile.sync.markdown_backend import MarkdownFileBackend

        # Use default file paths or get from config if specified
        changelog_file = self.config.get("integrations", {}).get("markdown", {}).get("changelog_file", "CHANGELOG.md")
        todo_file = self.config.get("integrations", {}).get("markdown", {}).get("todo_file", "TODO.md")

        return MarkdownFileBackend(
            changelog_file=changelog_file,
            todo_file=todo_file
        )

    def get_integration_backend(self, integration_name: str):
        """Get initialized backend instance for an integration."""
        # Special case for markdown backend
        if integration_name == "markdown":
            return self.get_default_backend()

        config = self.get_integration_config(integration_name)

        if not self.validate_integration(integration_name):
            raise ValueError(f"Invalid configuration for {integration_name}")

        # Import and initialize the appropriate backend
        if integration_name == "github":
            from planfile.integrations.github import GitHubBackend
            # Auto-fetch token from gh CLI if not provided or is unexpanded env var
            token = config.get("token", "")
            if not token or "${" in token:
                import subprocess
                try:
                    result = subprocess.run(
                        ["gh", "auth", "token"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        config = {**config, "token": result.stdout.strip()}
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass  # gh not installed or not authenticated
            return GitHubBackend(**config)
        elif integration_name == "gitlab":
            from planfile.integrations.gitlab import GitLabBackend
            return GitLabBackend(**config)
        elif integration_name == "jira":
            from planfile.integrations.jira import JiraBackend
            return JiraBackend(**config)

        raise ValueError(f"Unknown integration: {integration_name}")
