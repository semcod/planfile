"""
CI runner with automated bug-fix loop — ticket-aware refactor.

Merged logic from ci_runner.py (453L) + auto_loop.py display helpers.
Creates planfile tickets from test/analysis failures.
"""

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.runner import review_strategy


@dataclass
class TestResult:
    """Result of running tests."""
    passed: bool
    failed_tests: list[str]
    coverage: float
    metrics: dict[str, Any]
    output: str


@dataclass
class BugReport:
    """Generated bug report from test failures."""
    title: str
    description: str
    files: list[str]
    test_names: list[str]
    severity: str


class CIRunner:
    """CI/CD runner with automated bug-fix loop and ticket creation."""

    def __init__(
        self,
        strategy_path: str,
        project_path: str,
        backends: dict[str, Any] = None,
        llx_command: str = "llx",
        max_iterations: int = 10,
        auto_fix: bool = False,
        planfile_instance=None,
    ):
        self.strategy_path = Path(strategy_path)
        self.project_path = Path(project_path)
        self.backends = backends or {}
        self.llx_command = llx_command
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        self.strategy = load_strategy_yaml(strategy_path)
        self.iteration = 0

        # Optional planfile ticket integration
        self.pf = planfile_instance
        if self.pf is None:
            try:
                from planfile import Planfile
                self.pf = Planfile.auto_discover(str(self.project_path))
            except Exception:
                self.pf = None

    def run_tests(self) -> TestResult:
        """Run tests and return results."""
        cmd = [
            "python", "-m", "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-report=term-missing",
            "--junit-xml=test-results.xml",
            "-v"
        ]

        result = subprocess.run(
            cmd, cwd=self.project_path,
            capture_output=True, text=True
        )

        coverage = 0.0
        coverage_file = self.project_path / "coverage.json"
        if coverage_file.exists():
            coverage_data = json.loads(coverage_file.read_text())
            coverage = coverage_data.get("totals", {}).get("percent_covered", 0.0)

        failed_tests = []
        if result.returncode != 0:
            for line in result.stdout.split('\n'):
                if "FAILED" in line and "::" in line:
                    test_name = line.split("FAILED")[1].strip()
                    failed_tests.append(test_name)

        return TestResult(
            passed=result.returncode == 0,
            failed_tests=failed_tests,
            coverage=coverage,
            metrics={"coverage": coverage},
            output=result.stdout + result.stderr
        )

    def run_code_analysis(self) -> dict[str, Any]:
        """Run code2llm and vallm analysis."""
        metrics = {}

        try:
            result = subprocess.run(
                [self.llx_command, "analyze", "--run", "--json"],
                cwd=self.project_path, capture_output=True, text=True
            )
            if result.returncode == 0:
                metrics["code2llm"] = json.loads(result.stdout)
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["vallm", "validate", "--json"],
                cwd=self.project_path, capture_output=True, text=True
            )
            if result.returncode == 0:
                metrics["vallm"] = json.loads(result.stdout)
        except Exception:
            pass

        return metrics

    def generate_bug_report(self, test_result: TestResult, metrics: dict[str, Any]) -> BugReport:
        """Generate bug report using LLM."""
        context = {
            "failed_tests": test_result.failed_tests,
            "coverage": test_result.coverage,
            "metrics": metrics,
            "output": test_result.output[-2000:]
        }

        prompt = f"""
Based on the following test failures and code metrics, create a bug report:

Failed tests: {context['failed_tests']}
Coverage: {context['coverage']}%
Code metrics: {json.dumps(metrics, indent=2)}

Recent test output:
{context['output']}

Respond in JSON format:
{{"title": "...", "description": "...", "files": ["file1.py"], "severity": "high"}}
"""

        result = subprocess.run(
            [self.llx_command, "chat", "--model", "balanced", "--prompt", prompt],
            capture_output=True, text=True
        )

        try:
            bug_data = json.loads(result.stdout)
            return BugReport(
                title=bug_data["title"],
                description=bug_data["description"],
                files=bug_data.get("files", []),
                test_names=test_result.failed_tests,
                severity=bug_data.get("severity", "medium")
            )
        except Exception:
            return BugReport(
                title=f"Tests failed: {len(test_result.failed_tests)} failures",
                description=f"Tests failed: {', '.join(test_result.failed_tests)}",
                files=[], test_names=test_result.failed_tests,
                severity="medium"
            )

    def create_bug_tickets(self, bug_report: BugReport) -> list[str]:
        """Create bug tickets in configured backends AND local planfile."""
        ticket_urls = []

        # Create local planfile ticket
        if self.pf:
            try:
                from planfile import TicketSource
                ticket = self.pf.create_ticket(
                    title=bug_report.title,
                    priority="critical" if bug_report.severity in ("high", "critical") else "normal",
                    source=TicketSource(tool="ci-runner", context={
                        "error": bug_report.description[:500],
                        "files": bug_report.files,
                    }),
                    labels=["bug", "auto-generated", f"severity-{bug_report.severity}"],
                    description=bug_report.description,
                )
                ticket_urls.append(f"planfile:{ticket.id}")
            except Exception:
                pass

        # Create in external backends
        for name, backend in self.backends.items():
            try:
                ticket = backend.create_ticket(
                    title=bug_report.title,
                    description=bug_report.description,
                    labels=["bug", "auto-generated", f"severity-{bug_report.severity}"],
                    priority="high" if bug_report.severity in ("high", "critical") else "medium"
                )
                ticket_urls.append(ticket.url)
            except Exception:
                pass

        return ticket_urls

    def auto_fix_bugs(self, bug_report: BugReport) -> bool:
        """Attempt to auto-fix bugs using LLM."""
        if not self.auto_fix:
            return False

        prompt = f"""
Fix the following bug in the codebase:

Bug: {bug_report.title}
Description: {bug_report.description}
Failed tests: {bug_report.test_names}

Focus on the failed tests and make minimal changes to fix them.
"""

        result = subprocess.run(
            [self.llx_command, "chat", "--model", "local", "--prompt", prompt, "--execute"],
            cwd=self.project_path, capture_output=True, text=True
        )

        return result.returncode == 0

    def check_strategy_completion(self) -> tuple[bool, list[str]]:
        """Check if strategy goals are met."""
        review = review_strategy(
            strategy=self.strategy,
            project_path=str(self.project_path),
            backends=self.backends
        )

        issues = []
        summary = review.get("summary", {})

        if summary.get("total_tickets", 0) > summary.get("completed", 0):
            issues.append(f"Not all tickets completed: {summary['completed']}/{summary['total_tickets']}")

        if summary.get("blocked", 0) > 0:
            issues.append(f"{summary['blocked']} tickets are blocked")

        return len(issues) == 0, issues

    def run_loop(self) -> dict[str, Any]:
        """Run the main CI/CD loop."""
        results = {
            "iterations": [],
            "success": False,
            "total_iterations": 0,
            "tickets_created": [],
            "final_status": "failed"
        }

        for self.iteration in range(1, self.max_iterations + 1):
            iteration_result = {
                "iteration": self.iteration,
                "tests_passed": False,
                "tickets_created": [],
                "auto_fixed": False
            }

            test_result = self.run_tests()
            iteration_result["tests_passed"] = test_result.passed
            iteration_result["coverage"] = test_result.coverage

            if test_result.passed:
                strategy_complete, issues = self.check_strategy_completion()

                if strategy_complete:
                    results["success"] = True
                    results["final_status"] = "completed"
                    iteration_result["status"] = "completed"
                    results["iterations"].append(iteration_result)
                    break
            else:
                metrics = self.run_code_analysis()
                bug_report = self.generate_bug_report(test_result, metrics)
                ticket_urls = self.create_bug_tickets(bug_report)
                iteration_result["tickets_created"] = ticket_urls
                results["tickets_created"].extend(ticket_urls)

                if self.auto_fix:
                    fixed = self.auto_fix_bugs(bug_report)
                    iteration_result["auto_fixed"] = fixed

                iteration_result["status"] = "failed"

            results["iterations"].append(iteration_result)
            results["total_iterations"] = self.iteration

            if self.iteration < self.max_iterations:
                time.sleep(2)

        if not results["success"]:
            results["final_status"] = "max_iterations_reached"

        return results

    def save_results(self, results: dict[str, Any], output_path: str | None = None) -> None:
        """Save results to file."""
        if not output_path:
            output_path = self.project_path / "ci-results.json"
        Path(output_path).write_text(json.dumps(results, indent=2))
