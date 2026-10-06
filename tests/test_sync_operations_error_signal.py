"""Tests for error signaling in sync operations and outbound search."""

import logging
from unittest.mock import MagicMock

from planfile.sync.operations import _resolve_selected_remote_ids
from planfile.sync.outbound import _recover_lost_create


def test_resolve_selected_remote_ids_logs_debug_signal_on_sync_state_error(caplog):
    mock_sync_state = MagicMock()
    mock_sync_state.get_remote_id.side_effect = RuntimeError("Mocked sync_state failure")

    with caplog.at_level(logging.DEBUG):
        result = _resolve_selected_remote_ids(
            ticket_ids=["TICK-101"],
            sections=None,
            sync_state=mock_sync_state,
            integration_name="github",
        )

    assert "TICK-101" in result
    assert any("sync_state remote id lookup failed for ticket TICK-101" in record.message for record in caplog.records)
    assert any("Mocked sync_state failure" in record.message for record in caplog.records)


def test_recover_lost_create_logs_debug_signal_on_search_exception(caplog):
    mock_search = MagicMock(side_effect=RuntimeError("Search backend failure"))
    mock_backend = MagicMock()
    mock_backend.search_tickets = mock_search

    ticket = {"id": "TICK-202", "metadata": {"planfile_id": "PLF-999"}}

    with caplog.at_level(logging.DEBUG):
        result = _recover_lost_create(
            backend=mock_backend,
            ticket=ticket,
            ticket_id="TICK-202",
            integration_name="github",
        )

    assert result is None
    assert any("Remote ticket search for marker PLF-999 failed" in record.message for record in caplog.records)
    assert any("Search backend failure" in record.message for record in caplog.records)
