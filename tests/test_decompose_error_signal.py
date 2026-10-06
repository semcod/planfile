"""Tests for error logging signals on native graph acceleration fallbacks in decompose."""

import logging
from unittest.mock import MagicMock

import planfile.core.decompose as decompose
from planfile import Planfile
from planfile.core.decompose import (
    add_dependency,
    calculate_critical_priority,
    execution_waves,
    prune_dangling_dependencies,
    validate_ticket_dag,
)


def _pf(tmp_path):
    return Planfile(str(tmp_path))


def test_validate_ticket_dag_logs_debug_signal_on_native_error(tmp_path, monkeypatch, caplog):
    pf = _pf(tmp_path)
    pf.create_ticket(name="t1")

    mock_validate = MagicMock(side_effect=RuntimeError("Native validate crash"))
    monkeypatch.setattr(decompose, "HAS_RUST_GRAPH", True)
    monkeypatch.setattr(decompose, "_native_validate_dag", mock_validate)

    with caplog.at_level(logging.DEBUG):
        is_dag, cycles = validate_ticket_dag(pf)

    assert is_dag is True
    assert cycles == []
    assert any("Native DAG validation failed in validate_ticket_dag" in r.message for r in caplog.records)
    assert any("Native validate crash" in r.message for r in caplog.records)


def test_add_dependency_logs_debug_signal_on_native_error(tmp_path, monkeypatch, caplog):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")
    b = pf.create_ticket(name="b")

    mock_validate = MagicMock(side_effect=RuntimeError("Native validate crash in add_dependency"))
    monkeypatch.setattr(decompose, "HAS_RUST_GRAPH", True)
    monkeypatch.setattr(decompose, "_native_validate_dag", mock_validate)

    with caplog.at_level(logging.DEBUG):
        add_dependency(pf, b.id, after=[a.id])

    assert any("Native DAG validation failed in add_dependency" in r.message for r in caplog.records)
    assert any("Native validate crash in add_dependency" in r.message for r in caplog.records)
    assert pf.get_ticket(b.id).blocked_by == [a.id]


def test_prune_dangling_dependencies_logs_debug_signal_on_native_error(tmp_path, monkeypatch, caplog):
    pf = _pf(tmp_path)
    t = pf.create_ticket(name="t")
    pf.update_ticket(t.id, blocked_by=["GHOST-999"])

    mock_clean = MagicMock(side_effect=RuntimeError("Native clean ghost crash"))
    monkeypatch.setattr(decompose, "HAS_RUST_GRAPH", True)
    monkeypatch.setattr(decompose, "_native_clean_ghost", mock_clean)

    with caplog.at_level(logging.DEBUG):
        rep = prune_dangling_dependencies(pf)

    assert any("Native ghost cleaning failed in prune_dangling_dependencies" in r.message for r in caplog.records)
    assert any("Native clean ghost crash" in r.message for r in caplog.records)
    assert t.id in rep["unblocked"]
    assert pf.get_ticket(t.id).blocked_by == []


def test_execution_waves_logs_debug_signal_on_native_error(tmp_path, monkeypatch, caplog):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")
    b = pf.create_ticket(name="b", blocked_by=[a.id])

    mock_waves = MagicMock(side_effect=RuntimeError("Native execution layers crash"))
    monkeypatch.setattr(decompose, "HAS_RUST_GRAPH", True)
    monkeypatch.setattr(decompose, "_native_execution_layers", mock_waves)

    with caplog.at_level(logging.DEBUG):
        waves = execution_waves(pf)

    assert any("Native execution layers failed in execution_waves" in r.message for r in caplog.records)
    assert any("Native execution layers crash" in r.message for r in caplog.records)
    assert waves == [[a.id], [b.id]]


def test_calculate_critical_priority_logs_debug_signal_on_native_error(tmp_path, monkeypatch, caplog):
    pf = _pf(tmp_path)
    a = pf.create_ticket(name="a")

    mock_deps = MagicMock(side_effect=RuntimeError("Native transitive dependents crash"))
    monkeypatch.setattr(decompose, "HAS_RUST_GRAPH", True)
    monkeypatch.setattr(decompose, "_native_transitive_dependents", mock_deps)

    with caplog.at_level(logging.DEBUG):
        weights = calculate_critical_priority([a])

    assert any(f"Failed calculating native transitive dependents for ticket {a.id}" in r.message for r in caplog.records)
    assert any("Native transitive dependents crash" in r.message for r in caplog.records)
    assert weights[a.id] == 0
