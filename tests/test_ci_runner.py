"""Regression tests for CI runner LLX integration behavior."""

from pathlib import Path
from types import SimpleNamespace

from planfile.ci import BugReport, CIRunner, TestResult


def _make_runner(auto_fix: bool = False) -> CIRunner:
    runner = CIRunner.__new__(CIRunner)
    runner.llx_command = "llx"
    runner.project_path = Path(".")
    runner.auto_fix = auto_fix
    return runner


def test_generate_bug_report_accepts_title_key(monkeypatch):
    """Bug report parser accepts llx output with 'title' key."""
    runner = _make_runner()

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='{"title":"Fix failing test","description":"Handle edge case","files":["src/a.py"],"severity":"high"}',
            stderr="",
        )

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    test_result = TestResult(
        passed=False,
        failed_tests=["tests/test_mod.py::test_case"],
        coverage=72.5,
        metrics={},
        output="AssertionError",
    )

    report = runner.generate_bug_report(test_result, metrics={})

    assert report.name == "Fix failing test"
    assert report.description == "Handle edge case"
    assert report.files == ["src/a.py"]
    assert report.severity == "high"


def test_generate_bug_report_parses_markdown_json(monkeypatch):
    """Bug report parser handles markdown fenced JSON output."""
    runner = _make_runner()

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout='Here is result:\n```json\n{"name":"Fix parser","description":"Adjust parser path","files":["src/p.py"],"severity":"medium"}\n```',
            stderr="",
        )

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    test_result = TestResult(
        passed=False,
        failed_tests=["tests/test_parser.py::test_parse"],
        coverage=61.0,
        metrics={},
        output="ValueError",
    )

    report = runner.generate_bug_report(test_result, metrics={})

    assert report.name == "Fix parser"
    assert report.files == ["src/p.py"]


def test_auto_fix_bugs_uses_local_chat_without_execute(monkeypatch):
    """Auto-fix command no longer uses unsupported --execute flag."""
    runner = _make_runner(auto_fix=True)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    bug = BugReport(
        name="Fix auth bug",
        description="Null check missing",
        files=["src/auth.py"],
        test_names=["tests/test_auth.py::test_login"],
        severity="high",
    )

    assert runner.auto_fix_bugs(bug) is True
    assert "--local" in captured["cmd"]
    assert "--execute" not in captured["cmd"]
    assert any("Fix auth bug" in str(part) for part in captured["cmd"])
