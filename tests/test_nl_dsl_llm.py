"""Tests for NL-DSL-LLM pattern in planfile: parser, CLI ask/mcp, and MCP tools."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from planfile.cli.commands import app
from planfile.dsl.parser import DSLParser
from planfile.mcp.server import TOOLS, handle_tool_call

runner = CliRunner()


def test_parser_polish_verbs_and_objects():
    parser = DSLParser()

    cmd_list = parser.parse("pokaż otwarte zadania")
    assert cmd_list.verb == "list"
    assert cmd_list.object_type == "ticket"
    assert cmd_list.params.get("status") == "todo"

    cmd_create = parser.parse('dodaj zadanie "Nowa funkcja"')
    assert cmd_create.verb == "create"
    assert cmd_create.object_type == "ticket"
    assert cmd_create.target == "Nowa funkcja"

    cmd_done = parser.parse("zamknij zadanie #42")
    assert cmd_done.verb == "done"
    assert cmd_done.object_type == "ticket"
    assert cmd_done.target == "#42"

    cmd_delete = parser.parse("usuń zadanie #42")
    assert cmd_delete.verb == "delete"
    assert cmd_delete.object_type == "ticket"

    cmd_sync = parser.parse("synchronizuj")
    assert cmd_sync.verb == "sync"


def test_parser_english_verbs_and_objects():
    parser = DSLParser()

    cmd_list = parser.parse("show open tickets")
    assert cmd_list.verb == "show" or cmd_list.verb == "list"
    assert cmd_list.object_type == "ticket"
    assert cmd_list.params.get("status") == "todo"

    cmd_create = parser.parse('create ticket "Fix login bug" priority=high')
    assert cmd_create.verb == "create"
    assert cmd_create.object_type == "ticket"
    assert cmd_create.params.get("priority") == "high"

    cmd_done = parser.parse("done ticket #10")
    assert cmd_done.verb == "done"
    assert cmd_done.object_type == "ticket"


def test_parser_direct_dsl_format():
    parser = DSLParser()
    cmd = parser.parse("ticket.list status=open")
    assert cmd.verb == "list"
    assert cmd.object_type == "ticket"
    assert cmd.params.get("status") == "open"


def test_cli_ask_help():
    res = runner.invoke(app, ["ask", "--help"])
    assert res.exit_code == 0
    assert "Execute natural language query" in res.output or "ask" in res.output


def test_cli_mcp_help():
    res = runner.invoke(app, ["mcp", "--help"])
    assert res.exit_code == 0
    assert "Model Context Protocol" in res.output or "mcp" in res.output


def test_mcp_tools_manifest():
    tool_names = [t["name"] for t in TOOLS]
    assert "planfile_ask" in tool_names
    assert "planfile_describe_grammar" in tool_names
    assert "planfile_dsl" in tool_names


def test_mcp_describe_grammar():
    res = handle_tool_call("planfile_describe_grammar", {})
    assert "grammar" in res
    assert "pl" in res.get("supported_languages", [])
    assert res.get("standard") == "wellmanifest/nl-dsl-llm"
