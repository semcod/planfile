"""Tests for error signaling and exception handling in Planfile DSL executor."""
import logging
from unittest.mock import MagicMock, patch
import pytest

from planfile.dsl.executor import DSLExecutor


def test_translate_with_llm_exception_logs_debug_signal(caplog):
    mock_pf = MagicMock()
    executor = DSLExecutor()
    executor._pf = mock_pf

    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}), \
         patch("planfile.llm.client.call_llm", side_effect=RuntimeError("LLM API connection refused")), \
         caplog.at_level(logging.DEBUG):
        result = executor._translate_with_llm("pokaż zadania w sprincie")

    assert result is None
    assert any("Planfile LLM translation fallback failed" in record.message for record in caplog.records)
    assert any("LLM API connection refused" in record.message for record in caplog.records)


def test_conversational_blocked_queries_exception_logs_debug_signal(caplog):
    mock_pf = MagicMock()
    mock_pf.list_tickets.side_effect = RuntimeError("Storage database corrupted")
    executor = DSLExecutor()
    executor._pf = mock_pf

    with caplog.at_level(logging.DEBUG):
        res = executor._handle_conversational_query("co jest zablokowane")

    assert res is not None
    assert res.ok is True
    assert any("Failed to list tickets for blocked queries" in record.message for record in caplog.records)
    assert any("Storage database corrupted" in record.message for record in caplog.records)


def test_conversational_next_queries_exception_logs_debug_signal(caplog):
    mock_pf = MagicMock()
    mock_pf.list_tickets.side_effect = RuntimeError("I/O failure")
    executor = DSLExecutor()
    executor._pf = mock_pf

    with caplog.at_level(logging.DEBUG):
        res = executor._handle_conversational_query("co robic dalej")

    assert res is not None
    assert res.ok is True
    assert any("Failed to list tickets for next task queries" in record.message for record in caplog.records)
    assert any("I/O failure" in record.message for record in caplog.records)
