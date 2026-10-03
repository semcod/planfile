"""Tests for automatic synchronization on ticket creation."""

from unittest.mock import MagicMock, patch

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


class TestTicketCreateAutoSync:
    def test_auto_sync_triggered_when_github_configured(
        self, ticket_cli, initialized_repo
    ):
        # Create github integration config
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._auto_sync") as mock_sync:
            result = runner.invoke(ticket_cli, ["ticket", "create", "Auto sync test"])
            assert result.exit_code == 0
            assert "Created PLF-001: Auto sync test" in result.output
            assert mock_sync.called
            args, kwargs = mock_sync.call_args
            assert args[1] == ["github"]
            assert kwargs["ticket_ids"] == ["PLF-001"]

    def test_no_sync_flag_skips_sync_but_records_integration(
        self, ticket_cli, initialized_repo
    ):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._auto_sync") as mock_sync:
            result = runner.invoke(
                ticket_cli, ["ticket", "create", "No sync test", "--no-sync"]
            )
            assert result.exit_code == 0
            assert "Created PLF-001: No sync test" in result.output
            mock_sync.assert_not_called()

        pf = Planfile(str(initialized_repo))
        ticket = pf.get_ticket("PLF-001")
        assert ticket is not None
        assert ticket.integration == ["github"]

    def test_auto_sync_failure_is_graceful_when_implicit(
        self, ticket_cli, initialized_repo
    ):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch(
            "planfile.cli.groups.ticket.commands._auto_sync",
            side_effect=RuntimeError("Network offline"),
        ):
            result = runner.invoke(ticket_cli, ["ticket", "create", "Offline test"])
            assert result.exit_code == 0
            assert "Created PLF-001: Offline test" in result.output
            assert "Auto-sync failed" in result.output

    def test_explicit_sync_failure_raises(self, ticket_cli, initialized_repo):
        github_config = initialized_repo / ".planfile" / "github.planfile.yaml"
        github_config.write_text("integrations:\n  github:\n    repo: owner/repo\n")

        runner = CliRunner()
        with patch(
            "planfile.cli.groups.ticket.commands._auto_sync",
            side_effect=typer.Exit(1),
        ):
            result = runner.invoke(
                ticket_cli, ["ticket", "create", "Explicit fail", "--sync"]
            )
            assert result.exit_code == 1

    def test_no_sync_when_no_integrations_configured(
        self, ticket_cli, initialized_repo
    ):
        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._auto_sync") as mock_sync:
            result = runner.invoke(ticket_cli, ["ticket", "create", "Local only"])
            assert result.exit_code == 0
            assert "Created PLF-001: Local only" in result.output
            mock_sync.assert_not_called()

    def test_explicit_integration_option_triggers_sync(
        self, ticket_cli, initialized_repo
    ):
        runner = CliRunner()
        with patch("planfile.cli.groups.ticket.commands._auto_sync") as mock_sync:
            result = runner.invoke(
                ticket_cli, ["ticket", "create", "Explicit opt", "-i", "github"]
            )
            assert result.exit_code == 0
            assert "Created PLF-001: Explicit opt" in result.output
            assert mock_sync.called
            args, kwargs = mock_sync.call_args
            assert args[1] == ["github"]
            assert kwargs["ticket_ids"] == ["PLF-001"]
