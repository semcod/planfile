"""Tests for inbound synchronization before ticket creation."""

from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from planfile import Planfile
from planfile.cli.groups.ticket import register_ticket_commands


@pytest.fixture()
def ticket_cli():
    app = typer.Typer()
    register_ticket_commands(app)
    return app


@pytest.fixture()
def initialized_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pf = Planfile(str(tmp_path))
    pf.store.init()
    return tmp_path


class TestTicketCreateInboundSync:
    def test_inbound_sync_triggered_by_default_when_github_configured(
        self, ticket_cli, initialized_repo
    ):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._inbound_sync_before_create") as mock_inbound, \
             patch("planfile.cli.groups.ticket.commands._auto_sync"):
            result = runner.invoke(ticket_cli, ["ticket", "create", "Inbound sync check"])
            assert result.exit_code == 0
            assert mock_inbound.called
            args, kwargs = mock_inbound.call_args
            assert args[0] == str(initialized_repo)
            assert args[1] == ["github"]
            assert kwargs.get("dry_run") is False

    def test_no_inbound_sync_flag_skips_inbound_check(
        self, ticket_cli, initialized_repo
    ):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._inbound_sync_before_create") as mock_inbound, \
             patch("planfile.cli.groups.ticket.commands._auto_sync"):
            result = runner.invoke(
                ticket_cli, ["ticket", "create", "Skip inbound", "--no-inbound-sync"]
            )
            assert result.exit_code == 0
            mock_inbound.assert_not_called()

    def test_inbound_sync_failure_does_not_block_ticket_creation(
        self, ticket_cli, initialized_repo
    ):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch(
            "planfile.cli.groups.sync.core.sync_integration",
            side_effect=RuntimeError("GitHub API rate limit exceeded"),
        ), patch("planfile.cli.groups.ticket.commands._auto_sync"):
            result = runner.invoke(ticket_cli, ["ticket", "create", "Resilient ticket"])
            assert result.exit_code == 0
            assert "Created PLF-001: Resilient ticket" in result.output
            assert "Inbound sync from github skipped" in result.output
