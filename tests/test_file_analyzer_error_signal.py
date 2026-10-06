"""Tests for error signaling and exception propagation in file analyzer."""
import logging
from unittest.mock import patch

import pytest

from planfile.analysis.file_analyzer import FileAnalyzer


def test_native_analyzer_exception_logs_debug_signal_and_falls_back(tmp_path, caplog):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("TODO: fix this issue\n", encoding="utf-8")

    analyzer = FileAnalyzer()

    with patch("planfile.analysis.file_analyzer.HAS_RUST_ANALYZER", True), \
         patch("planfile.analysis.file_analyzer._native_analyze_file", side_effect=RuntimeError("Native crash simulation")), \
         caplog.at_level(logging.DEBUG):
        issues, metrics, tasks = analyzer.analyze_file(test_file)

    # Verifies error signal was logged
    assert any("Native file analyzer failed" in record.message for record in caplog.records)
    assert any("Native crash simulation" in record.message for record in caplog.records)
    # Verifies fallback to text analysis succeeded
    assert isinstance(issues, list)
    assert isinstance(metrics, list)
    assert isinstance(tasks, list)


def test_native_analyzer_timeout_error_is_propagated(tmp_path):
    test_file = tmp_path / "sample.txt"
    test_file.write_text("content", encoding="utf-8")

    analyzer = FileAnalyzer()

    with patch("planfile.analysis.file_analyzer.HAS_RUST_ANALYZER", True), \
         patch("planfile.analysis.file_analyzer._native_analyze_file", side_effect=TimeoutError("Analysis timed out")):
        with pytest.raises(TimeoutError, match="Analysis timed out"):
            analyzer.analyze_file(test_file)
