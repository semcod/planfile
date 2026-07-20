"""Regression tests for CI runner LLX integration behavior."""

from pathlib import Path
from types import SimpleNamespace

from planfile.ci import BugReport, CIRunner, TestResult


def _make_runner(auto_fix: bool = False) -> CIRunner:
    runner = CIRunner.__new__(CIRunner)
    runner.llx_command = "llx"
    runner.project_path = Path(".")
    runner.auto_fix = auto_fix
    runner.dry_run = False
    return runner


def test_run_tests_collects_coverage_for_planfile_package(monkeypatch, tmp_path):
    """CI runner measures the installed package, not a non-existent src directory."""
    runner = _make_runner()
    runner.project_path = tmp_path
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        (tmp_path / "coverage.json").write_text(
            '{"totals":{"percent_covered":87.5}}',
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="passed", stderr="")

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    result = runner.run_tests()

    assert "--cov=planfile" in captured["cmd"]
    assert "--cov=src" not in captured["cmd"]
    assert result.passed is True
    assert result.coverage == 87.5


def test_check_strategy_completion_without_backend_is_successful():
    """The documented no-backend dry-run path must not require a default backend."""
    runner = _make_runner()
    runner.backends = {}

    assert runner.check_strategy_completion() == (True, [])


def test_check_strategy_completion_uses_configured_backend(monkeypatch):
    """A single named backend is selected instead of looking for a 'default' key."""
    runner = _make_runner()
    runner.backends = {"github": object()}
    runner.strategy = object()
    captured = {}

    def fake_review_strategy(**kwargs):
        captured.update(kwargs)
        return {"summary": {"total_tickets": 0, "completed": 0, "blocked": 0}}

    monkeypatch.setattr("planfile.ci.review_strategy", fake_review_strategy)

    assert runner.check_strategy_completion() == (True, [])
    assert captured["backend_name"] == "github"


def test_run_loop_counts_successful_first_iteration(monkeypatch):
    """Successful first iteration is reported as one iteration, not zero."""
    runner = _make_runner()
    runner.max_iterations = 3
    runner.backends = {}
    monkeypatch.setattr(
        runner,
        "run_tests",
        lambda: TestResult(True, [], 90.0, {}, "passed"),
    )

    results = runner.run_loop()

    assert results["success"] is True
    assert results["total_iterations"] == 1


def test_create_bug_tickets_dry_run_has_no_side_effects():
    """Dry-run mode must not create local or remote tickets."""
    runner = _make_runner()
    runner.dry_run = True
    runner.pf = SimpleNamespace(create_ticket=lambda **kwargs: (_ for _ in ()).throw(AssertionError))
    runner.backends = {
        "github": SimpleNamespace(
            create_ticket=lambda **kwargs: (_ for _ in ()).throw(AssertionError)
        )
    }
    bug = BugReport(
        name="Dry-run bug",
        description="Must not be persisted",
        files=[],
        test_names=["tests/test_dry_run.py::test_case"],
        severity="medium",
    )

    assert runner.create_bug_tickets(bug) == []


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


def test_auto_fix_bugs_uses_llx_plan_run_with_edit_backend(monkeypatch, tmp_path):
    """Auto-fix uses llx plan run + editing backend and checks YAML stdout payload."""
    runner = _make_runner(auto_fix=True)
    runner.project_path = tmp_path

    src_file = tmp_path / "src" / "auth.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("def login():\n    return True\n", encoding="utf-8")

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        stdout = (
            "strategy: ci-autofix.planfile.yaml\n"
            "project: .\n"
            "summary:\n"
            "  success: 1\n"
            "  failed: 0\n"
            "results:\n"
            "- ticket_id: ci-autofix-123\n"
            "  task_name: Fix auth bug\n"
            "  status: success\n"
            "  file_changed: true\n"
        )
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    bug = BugReport(
        name="Fix auth bug",
        description="Null check missing",
        files=["src/auth.py"],
        test_names=["tests/test_auth.py::test_login"],
        severity="high",
    )

    assert runner.auto_fix_bugs(bug) is True
    assert captured["cmd"][:3] == ["llx", "plan", "run"]
    assert "--format" in captured["cmd"]
    assert "yaml" in captured["cmd"]
    assert "--ticket-id" in captured["cmd"]
    assert "--use-aider" in captured["cmd"]
    assert "--output-yaml" not in captured["cmd"]
    assert captured["kwargs"]["cwd"] == tmp_path


def test_auto_fix_bugs_returns_false_without_target_file(monkeypatch, tmp_path):
    """Auto-fix is skipped when no usable target file is available."""
    runner = _make_runner(auto_fix=True)
    runner.project_path = tmp_path

    called = {"value": False}

    def fake_run(cmd, **kwargs):
        called["value"] = True
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr("planfile.ci.subprocess.run", fake_run)

    bug = BugReport(
        name="Fix unknown bug",
        description="No target file provided",
        files=[],
        test_names=["tests/test_unknown.py::test_case"],
        severity="medium",
    )

    assert runner.auto_fix_bugs(bug) is False
    assert called["value"] is False
