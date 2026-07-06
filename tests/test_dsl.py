"""Tests for planfile DSL parser and executor."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from planfile.dsl.parser import DSLParser, DSLCommand
from planfile.dsl.executor import DSLExecutor, DSLResult


# ── Parser tests ───────────────────────────────────────────────────────────────

class TestDSLParser:
    def setup_method(self):
        self.parser = DSLParser()

    def test_parse_empty(self):
        cmd = self.parser.parse("")
        assert cmd.verb == "help"

    def test_parse_help(self):
        cmd = self.parser.parse("help")
        assert cmd.verb == "help"

    def test_parse_unknown_verb(self):
        cmd = self.parser.parse("frobnicate ticket PLF-001")
        assert cmd.verb == "unknown"

    def test_parse_list_tickets(self):
        cmd = self.parser.parse("list tickets")
        assert cmd.verb == "list"
        assert cmd.object_type == "ticket"

    def test_parse_list_tickets_with_filters(self):
        cmd = self.parser.parse("list tickets sprint=current status=open")
        assert cmd.verb == "list"
        assert cmd.object_type == "ticket"
        assert cmd.params["sprint"] == "current"
        assert cmd.params["status"] == "open"

    def test_parse_list_sprints(self):
        cmd = self.parser.parse("list sprints")
        assert cmd.verb == "list"
        assert cmd.object_type == "sprint"

    def test_parse_create_ticket_quoted(self):
        cmd = self.parser.parse('create ticket "Fix login bug" priority=high')
        assert cmd.verb == "create"
        assert cmd.object_type == "ticket"
        assert cmd.target == "Fix login bug"
        assert cmd.params["priority"] == "high"

    def test_parse_create_ticket_sprint(self):
        cmd = self.parser.parse("create ticket MyTask sprint=2 priority=critical")
        assert cmd.verb == "create"
        assert cmd.target == "MyTask"
        assert cmd.params["sprint"] == 2
        assert cmd.params["priority"] == "critical"

    def test_parse_create_aliases(self):
        for alias in ("add", "new"):
            cmd = self.parser.parse(f'{alias} ticket "New task"')
            assert cmd.verb == "create"

    def test_parse_show_ticket(self):
        cmd = self.parser.parse("show ticket PLF-001")
        assert cmd.verb == "show"
        assert cmd.object_type == "ticket"
        assert cmd.target == "PLF-001"

    def test_parse_ticket_id_uppercase(self):
        cmd = self.parser.parse("show ticket plf-001")
        assert cmd.target == "PLF-001"

    def test_parse_update_ticket(self):
        cmd = self.parser.parse("update ticket PLF-001 status=done")
        assert cmd.verb == "update"
        assert cmd.target == "PLF-001"
        assert cmd.params["status"] == "done"

    def test_parse_set_alias(self):
        cmd = self.parser.parse("set ticket PLF-002 priority=critical")
        assert cmd.verb == "update"
        assert cmd.target == "PLF-002"
        assert cmd.params["priority"] == "critical"

    def test_parse_set_labels(self):
        cmd = self.parser.parse("set ticket PLF-003 labels=backend,auth,security")
        assert cmd.params["labels"] == ["backend", "auth", "security"]

    def test_parse_move_ticket(self):
        cmd = self.parser.parse("move ticket PLF-001 to sprint=2")
        assert cmd.verb == "move"
        assert cmd.target == "PLF-001"
        assert cmd.params.get("sprint") == 2 or cmd.params.get("to") == "sprint=2"

    def test_parse_move_ticket_to_value(self):
        cmd = self.parser.parse("move ticket PLF-001 to=3")
        assert cmd.verb == "move"
        assert cmd.target == "PLF-001"

    def test_parse_done(self):
        cmd = self.parser.parse("done ticket PLF-005")
        assert cmd.verb == "done"
        assert cmd.target == "PLF-005"

    def test_parse_done_aliases(self):
        for alias in ("finish", "complete"):
            cmd = self.parser.parse(f"{alias} ticket PLF-001")
            assert cmd.verb == "done"

    def test_parse_start(self):
        cmd = self.parser.parse("start ticket PLF-007")
        assert cmd.verb == "start"
        assert cmd.target == "PLF-007"

    def test_parse_block(self):
        cmd = self.parser.parse('block ticket PLF-008 reason="Waiting for API"')
        assert cmd.verb == "block"
        assert cmd.target == "PLF-008"
        assert "reason" in cmd.params

    def test_parse_delete(self):
        cmd = self.parser.parse("delete ticket PLF-010")
        assert cmd.verb == "delete"
        assert cmd.target == "PLF-010"

    def test_parse_delete_aliases(self):
        for alias in ("remove", "rm", "del"):
            cmd = self.parser.parse(f"{alias} ticket PLF-001")
            assert cmd.verb == "delete"

    def test_parse_validate(self):
        cmd = self.parser.parse("validate")
        assert cmd.verb == "validate"

    def test_parse_sync(self):
        cmd = self.parser.parse("sync github")
        assert cmd.verb == "sync"
        assert cmd.target == "github"

    def test_parse_sync_all(self):
        cmd = self.parser.parse("sync all")
        assert cmd.verb == "sync"

    def test_parse_query_where(self):
        cmd = self.parser.parse("query tickets where priority=high status=open")
        assert cmd.verb == "query"
        assert cmd.object_type == "ticket"
        assert cmd.params.get("priority") == "high"
        assert cmd.params.get("status") == "open"

    def test_parse_export(self):
        cmd = self.parser.parse("export format=yaml")
        assert cmd.verb == "export"
        assert cmd.params["format"] == "yaml"

    def test_coerce_bool_true(self):
        cmd = self.parser.parse("create ticket Test dry_run=true")
        assert cmd.params.get("dry_run") is True

    def test_coerce_bool_false(self):
        cmd = self.parser.parse("create ticket Test sync=false")
        assert cmd.params.get("sync") is False

    def test_coerce_int(self):
        cmd = self.parser.parse("list tickets sprint=3")
        assert cmd.params["sprint"] == 3

    def test_to_dict(self):
        cmd = DSLCommand(verb="list", object_type="ticket", target=None, params={"sprint": "current"})
        d = cmd.to_dict()
        assert d["verb"] == "list"
        assert d["object_type"] == "ticket"
        assert d["params"] == {"sprint": "current"}

    def test_is_valid(self):
        cmd = DSLCommand(verb="list")
        assert cmd.is_valid
        empty = DSLCommand(verb="")
        assert not empty.is_valid


# ── Executor tests (with mocked Planfile) ─────────────────────────────────────

def _make_mock_ticket(ticket_id="PLF-001", name="Test ticket", status="open", priority="normal"):
    t = MagicMock()
    t.id = ticket_id
    t.name = name
    t.status = status
    t.priority = priority
    t.model_dump.return_value = {
        "id": ticket_id, "name": name, "status": status, "priority": priority
    }
    return t


class TestDSLExecutor:
    def _executor_with_mock(self):
        executor = DSLExecutor.__new__(DSLExecutor)
        executor._project_path = "."
        executor._pf = MagicMock()
        executor._parser = DSLParser()
        return executor

    def test_help(self):
        ex = self._executor_with_mock()
        result = ex.run("help")
        assert result.ok
        assert result.message is not None
        assert "create ticket" in result.message

    def test_unknown_verb(self):
        ex = self._executor_with_mock()
        result = ex.run("frobnicate things")
        assert not result.ok
        assert "Unrecognized command" in (result.error or "")

    def test_list_tickets(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket()
        ex._pf.list_tickets.return_value = [ticket]
        result = ex.run("list tickets sprint=current")
        assert result.ok
        assert len(result.data) == 1
        assert result.data[0]["id"] == "PLF-001"

    def test_list_tickets_empty(self):
        ex = self._executor_with_mock()
        ex._pf.list_tickets.return_value = []
        result = ex.run("list tickets")
        assert result.ok
        assert result.data == []
        assert "0 ticket" in result.message

    def test_create_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket("PLF-002", "Fix login bug")
        ex._pf.create_ticket.return_value = ticket
        result = ex.run('create ticket "Fix login bug" priority=high')
        assert result.ok
        assert "PLF-002" in result.message
        ex._pf.create_ticket.assert_called_once()

    def test_create_ticket_missing_name(self):
        ex = self._executor_with_mock()
        result = ex.run("create ticket")
        assert not result.ok
        assert "name required" in (result.error or "").lower()

    def test_show_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket()
        ex._pf.get_ticket.return_value = ticket
        result = ex.run("show ticket PLF-001")
        assert result.ok
        assert result.data["id"] == "PLF-001"

    def test_show_ticket_not_found(self):
        ex = self._executor_with_mock()
        ex._pf.get_ticket.return_value = None
        result = ex.run("show ticket PLF-999")
        assert not result.ok
        assert "not found" in (result.error or "").lower()

    def test_show_ticket_missing_id(self):
        ex = self._executor_with_mock()
        result = ex.run("show ticket")
        assert not result.ok

    def test_update_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket(status="done")
        ex._pf.update_ticket.return_value = ticket
        result = ex.run("update ticket PLF-001 status=done")
        assert result.ok
        ex._pf.update_ticket.assert_called_with("PLF-001", status="done")

    def test_update_ticket_no_params(self):
        ex = self._executor_with_mock()
        result = ex.run("update ticket PLF-001")
        assert not result.ok
        assert "No fields" in (result.error or "")

    def test_update_ticket_not_found(self):
        ex = self._executor_with_mock()
        ex._pf.update_ticket.return_value = None
        result = ex.run("update ticket PLF-001 status=done")
        assert not result.ok

    def test_done_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket(status="done")
        ex._pf.update_ticket.return_value = ticket
        result = ex.run("done ticket PLF-001")
        assert result.ok
        ex._pf.update_ticket.assert_called_with("PLF-001", status="done")

    def test_start_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket(status="in_progress")
        ex._pf.update_ticket.return_value = ticket
        result = ex.run("start ticket PLF-001")
        assert result.ok
        ex._pf.update_ticket.assert_called_with("PLF-001", status="in_progress")

    def test_block_ticket(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket(status="blocked")
        ex._pf.block_ticket.return_value = ticket
        result = ex.run("block ticket PLF-001")
        assert result.ok
        ex._pf.block_ticket.assert_called_with("PLF-001", reason=None)

    def test_block_ticket_with_reason(self):
        ex = self._executor_with_mock()
        ticket = _make_mock_ticket(status="blocked")
        ex._pf.block_ticket.return_value = ticket
        result = ex.run('block ticket PLF-001 reason="API down"')
        assert result.ok
        ex._pf.block_ticket.assert_called_with("PLF-001", reason="API down")

    def test_delete_ticket(self):
        ex = self._executor_with_mock()
        ex._pf.delete_ticket.return_value = True
        result = ex.run("delete ticket PLF-001")
        assert result.ok
        assert result.data["deleted"] == "PLF-001"

    def test_delete_ticket_not_found(self):
        ex = self._executor_with_mock()
        ex._pf.delete_ticket.return_value = False
        result = ex.run("delete ticket PLF-999")
        assert not result.ok

    def test_move_ticket(self):
        ex = self._executor_with_mock()
        ex._pf.store.move_ticket.return_value = True
        result = ex.run("move ticket PLF-001 to=2")
        assert result.ok
        assert result.data["ticket_id"] == "PLF-001"

    def test_move_ticket_missing_sprint(self):
        ex = self._executor_with_mock()
        result = ex.run("move ticket PLF-001")
        assert not result.ok
        assert "sprint" in (result.error or "").lower()

    def test_dsl_result_to_dict(self):
        r = DSLResult(ok=True, command={"verb": "list"}, data=[1, 2], message="ok")
        d = r.to_dict()
        assert d["ok"] is True
        assert d["data"] == [1, 2]
        assert d["error"] is None

    def test_query_delegates_to_list(self):
        ex = self._executor_with_mock()
        ex._pf.list_tickets.return_value = []
        result = ex.run("query tickets where status=open")
        assert result.ok
        ex._pf.list_tickets.assert_called_once()

    def test_executor_handles_exception(self):
        ex = self._executor_with_mock()
        ex._pf.list_tickets.side_effect = RuntimeError("DB error")
        result = ex.run("list tickets")
        assert not result.ok
        assert "DB error" in (result.error or "")
