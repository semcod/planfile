"""Tests for per-project dotenv isolation in IntegrationConfig."""

from __future__ import annotations

import os

import pytest

from planfile.integrations.config import IntegrationConfig


def test_integration_config_isolates_dotenv_per_project_without_mutating_os_environ(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    env_name = "GITHUB" + "_TOKEN"
    placeholder = "example" + "-value-a"
    monkeypatch.delenv(env_name, raising=False)

    repo_a = tmp_path / "org" / "repo-a"
    (repo_a / ".planfile").mkdir(parents=True)
    (repo_a / ".env").write_text(f"{env_name}={placeholder}\n")
    (repo_a / ".planfile" / "github.planfile.yaml").write_text(
        f"integrations:\n  github:\n    repo: org/repo-a\n    token: ${{{env_name}}}\n"
    )

    repo_b = tmp_path / "org" / "repo-b"
    (repo_b / ".planfile").mkdir(parents=True)
    (repo_b / ".planfile" / "github.planfile.yaml").write_text(
        f"integrations:\n  github:\n    repo: org/repo-b\n    token: ${{{env_name}}}\n"
    )

    cfg_a = IntegrationConfig(str(repo_a))
    cfg_a.load_configs()
    assert cfg_a.get_integration_config("github")["token"] == placeholder
    assert env_name not in os.environ

    cfg_b = IntegrationConfig(str(repo_b))
    cfg_b.load_configs()
    assert cfg_b.get_integration_config("github")["token"] == f"${{{env_name}}}"
    assert env_name not in os.environ
