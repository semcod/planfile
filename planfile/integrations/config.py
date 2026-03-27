"""Configuration management for integrations with support for multiple config files."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import re


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
    
    def discover_configs(self) -> List[Path]:
        """Discover all *.planfile.yaml files in the directory."""
        configs = []
        for pattern in ["*.planfile.yaml", "*.planfile.yml"]:
            configs.extend(self.directory.glob(pattern))
        return sorted(configs)
    
    def load_configs(self) -> Dict[str, Any]:
        """Load and merge all configuration files."""
        self.config = {}
        
        # Load integration configs first (e.g., github.planfile.yaml)
        for config_file in self.discover_configs():
            if config_file.name.startswith("tickets."):
                continue  # Skip ticket files for now
                
            with open(config_file, 'r') as f:
                file_config = yaml.safe_load(f) or {}
                # Expand environment variables in the loaded config
                file_config = self._expand_env_vars(file_config)
                self._deep_merge(self.config, file_config)
        
        # Load ticket configs last
        for config_file in self.discover_configs():
            if config_file.name.startswith("tickets."):
                with open(config_file, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    # Expand environment variables in the loaded config
                    file_config = self._expand_env_vars(file_config)
                    self._deep_merge(self.config, file_config)
        
        return self.config
    
    def get_integration_config(self, integration_name: str) -> Dict[str, Any]:
        """Get configuration for a specific integration."""
        if not self.config:
            self.load_configs()
        
        return self.config.get("integrations", {}).get(integration_name, {})
    
    def get_project_config(self) -> Dict[str, Any]:
        """Get project configuration."""
        if not self.config:
            self.load_configs()
        
        return self.config.get("project", {})
    
    def get_sprint_config(self) -> Dict[str, Any]:
        """Get sprint configuration."""
        if not self.config:
            self.load_configs()
        
        return self.config.get("sprint", {})
    
    def get_backlog_config(self) -> Dict[str, Any]:
        """Get backlog configuration."""
        if not self.config:
            self.load_configs()
        
        return self.config.get("backlog", {})
    
    def _deep_merge(self, base: Dict, update: Dict):
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
            return False
        
        # Check for required fields based on integration type
        if integration_name == "github":
            return "repo" in config
        elif integration_name == "gitlab":
            return "url" in config and "project_id" in config
        elif integration_name == "jira":
            return "url" in config and "project" in config
        
        return True
    
    def get_integration_backend(self, integration_name: str):
        """Get initialized backend instance for an integration."""
        config = self.get_integration_config(integration_name)
        
        if not self.validate_integration(integration_name):
            raise ValueError(f"Invalid configuration for {integration_name}")
        
        # Import and initialize the appropriate backend
        if integration_name == "github":
            from planfile.integrations.github import GitHubBackend
            return GitHubBackend(**config)
        elif integration_name == "gitlab":
            from planfile.integrations.gitlab import GitLabBackend
            return GitLabBackend(**config)
        elif integration_name == "jira":
            from planfile.integrations.jira import JiraBackend
            return JiraBackend(**config)
        
        raise ValueError(f"Unknown integration: {integration_name}")
