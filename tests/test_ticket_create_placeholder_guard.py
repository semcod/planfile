"""Guard against creating tickets with unfilled template placeholders.

Automated callers (e.g. gate-capture workflows) sometimes copy example
commands verbatim, producing tickets titled
``[gate-finding:<finding_key>] <gate> gate failure``. ``ticket create``
must reject those unless ``--force`` is passed.
"""

import typer
import pytest
from typer.testing import CliRunner

from planfile.cli.groups.ticket import register_ticket_commands
from planfile.cli.groups.ticket.commands import _find_template_placeholders


class TestFindTemplatePlaceholders:
    def test_detects_simple_placeholder(self):
        assert _find_template_placeholders("[gate-finding:<finding_key>] failure") == ["<finding_key>"]

    def test_detects_multiword_placeholder(self):
        found = _find_template_placeholders("<exact line + command + next step>")
        assert found == ["<exact line + command + next step>"]

    def test_detects_across_name_and_description(self):
        found = _find_template_placeholders("<gate> gate failure", "next: <next step>")
        assert set(found) == {"<gate>", "<next step>"}

    def test_ignores_regular_text(self):
        assert _find_template_placeholders("Fix CC in src/koru/init.py", "cc: 13 (target: <= 10)") == []

    def test_ignores_none_and_empty(self):
        assert _find_template_placeholders(None, "") == []

    def test_ignores_uppercase_generics(self):
        # Type-like tokens such as list<T> or <HTML> are not lowercase
        # template placeholders and must not trigger the guard.
        assert _find_template_placeholders("Support list<T> in parser", "<HTML> handling") == []


@pytest.fixture()
def ticket_cli():
    app = typer.Typer()
    register_ticket_commands(app)
    return app


class TestTicketCreatePlaceholderGuard:
    def test_rejects_placeholder_title(self, ticket_cli):
        runner = CliRunner()
        result = runner.invoke(
            ticket_cli,
            ["ticket", "create", "[gate-finding:<finding_key>] <gate> gate failure",
             "--description", "<exact line + command + next step>"],
        )
        assert result.exit_code == 2
        assert "unfilled template placeholders" in result.output

    def test_force_bypasses_guard(self, ticket_cli, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(
            ticket_cli,
            ["ticket", "create", "<gate> gate failure", "--force"],
        )
        # The guard must not be the reason for failure; auto-discovery may
        # still fail in an empty tmp dir, but never with the guard message.
        assert "unfilled template placeholders" not in result.output
