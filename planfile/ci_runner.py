"""
Automated CI/CD integration for sprintstrat + llx.
Handles bug-fix loop: tests → tickets → fixes → retests.
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import time

from planfile.models import Strategy, TaskPattern, TaskType
from planfile.runner import apply_strategy_to_tickets, review_strategy
from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.integrations.github import GitHubBackend
from planfile.integrations.jira import JiraBackend
from planfile.integrations.gitlab import GitLabBackend


@dataclass
class TestResult:
    """Result of running tests."""
    passed: bool
    failed_tests: List[str]
    coverage: float
    metrics: Dict[str, Any]
    output: str


@dataclass
class BugReport:
    """Generated bug report from test failures."""
    title: str
    description: str
    files: List[str]
    test_names: List[str]
    severity: str


class CIRunner:
    """CI/CD runner with automated bug-fix loop."""
    
    def __init__(
        self,
        strategy_path: str,
        project_path: str,
        backends: Dict[str, Any],
        llx_command: str = "llx",
        max_iterations: int = 10,
        auto_fix: bool = False
    ):
        """
        Initialize CI runner.
        
        Args:
            strategy_path: Path to strategy YAML
            project_path: Project directory
            backends: PM system backends
            llx_command: LLX command to use
            max_iterations: Max loop iterations
            auto_fix: Whether to auto-fix with LLM
        """
        self.strategy_path = Path(strategy_path)
        self.project_path = Path(project_path)
        self.backends = backends
        self.llx_command = llx_command
        self.max_iterations = max_iterations
        self.auto_fix = auto_fix
        self.strategy = load_strategy_yaml(strategy_path)
        self.iteration = 0
        
    def run_tests(self) -> TestResult:
        """Run tests and return results."""
        print(f"🧪 Running tests (iteration {self.iteration})...")
        
        # Run pytest with coverage
        cmd = [
            "python", "-m", "pytest",
            "--cov=src",
            "--cov-report=json",
            "--cov-report=term-missing",
            "--junit-xml=test-results.xml",
            "-v"
        ]
        
        result = subprocess.run(
            cmd,
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        # Parse coverage
        coverage = 0.0
        coverage_file = self.project_path / "coverage.json"
        if coverage_file.exists():
            coverage_data = json.loads(coverage_file.read_text())
            coverage = coverage_data.get("totals", {}).get("percent_covered", 0.0)
        
        # Parse failed tests
        failed_tests = []
        if result.returncode != 0:
            # Parse from output
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
    
    def run_code_analysis(self) -> Dict[str, Any]:
        """Run code2llm and vallm analysis."""
        print("🔍 Running code analysis...")
        
        metrics = {}
        
        # Run code2llm
        try:
            result = subprocess.run(
                [self.llx_command, "analyze", "--run", "--json"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["code2llm"] = json.loads(result.stdout)
        except:
            pass
        
        # Run vallm
        try:
            result = subprocess.run(
                ["vallm", "validate", "--json"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["vallm"] = json.loads(result.stdout)
        except:
            pass
        
        return metrics
    
    def generate_bug_report(self, test_result: TestResult, metrics: Dict[str, Any]) -> BugReport:
        """Generate bug report using LLM."""
        print("🤖 Generating bug report with LLM...")
        
        # Prepare context for LLM
        context = {
            "failed_tests": test_result.failed_tests,
            "coverage": test_result.coverage,
            "metrics": metrics,
            "output": test_result.output[-2000:]  # Last 2000 chars
        }
        
        prompt = f"""
Based on the following test failures and code metrics, create a bug report:

Failed tests: {context['failed_tests']}
Coverage: {context['coverage']}%
Code metrics: {json.dumps(metrics, indent=2)}

Recent test output:
{context['output']}

Generate a bug report with:
1. Clear title describing the issue
2. Detailed description including reproduction steps
3. List of affected files (if any)
4. Severity level (low/medium/high/critical)
5. Suggested fix approach

Respond in JSON format:
{{
    "title": "...",
    "description": "...",
    "files": ["file1.py", "file2.py"],
    "severity": "high"
}}
"""
        
        # Call LLM
        result = subprocess.run(
            [self.llx_command, "chat", "--model", "balanced", "--prompt", prompt],
            capture_output=True,
            text=True
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
        except:
            # Fallback
            return BugReport(
                title=f"Tests failed: {len(test_result.failed_tests)} failures",
                description=f"Tests failed: {', '.join(test_result.failed_tests)}",
                files=[],
                test_names=test_result.failed_tests,
                severity="medium"
            )
    
    def create_bug_tickets(self, bug_report: BugReport) -> List[str]:
        """Create bug tickets in configured backends."""
        print(f"🎫 Creating bug tickets: {bug_report.title}")
        
        ticket_urls = []
        
        for name, backend in self.backends.items():
            try:
                # Create ticket
                ticket = backend.create_ticket(
                    title=bug_report.title,
                    description=bug_report.description,
                    labels=["bug", "auto-generated", f"severity-{bug_report.severity}"],
                    priority="high" if bug_report.severity in ["high", "critical"] else "medium"
                )
                ticket_urls.append(ticket.url)
                print(f"  ✓ Created ticket in {name}: {ticket.url}")
            except Exception as e:
                print(f"  ✗ Failed to create ticket in {name}: {e}")
        
        return ticket_urls
    
    def auto_fix_bugs(self, bug_report: BugReport) -> bool:
        """Attempt to auto-fix bugs using LLM."""
        if not self.auto_fix:
            return False
            
        print("🔧 Attempting auto-fix...")
        
        prompt = f"""
Fix the following bug in the codebase:

Bug: {bug_report.title}
Description: {bug_report.description}
Failed tests: {bug_report.test_names}

Please:
1. Analyze the issue
2. Identify the root cause
3. Provide the fix
4. Write the corrected code

Focus on the failed tests and make minimal changes to fix them.
"""
        
        # Try to fix with LLM
        result = subprocess.run(
            [self.llx_command, "chat", "--model", "local", "--prompt", prompt, "--execute"],
            cwd=self.project_path,
            capture_output=True,
            text=True
        )
        
        return result.returncode == 0
    
    def check_strategy_completion(self) -> Tuple[bool, List[str]]:
        """Check if strategy goals are met."""
        print("📊 Checking strategy completion...")
        
        # Review strategy
        review = review_strategy(
            strategy=self.strategy,
            project_path=str(self.project_path),
            backends=self.backends
        )
        
        # Check if all tickets are done
        issues = []
        summary = review.get("summary", {})
        
        if summary.get("total_tickets", 0) > summary.get("completed", 0):
            issues.append(f"Not all tickets completed: {summary['completed']}/{summary['total_tickets']}")
        
        if summary.get("blocked", 0) > 0:
            issues.append(f"{summary['blocked']} tickets are blocked")
        
        # Check quality goals
        for goal in self.planfile.goal.quality:
            if "coverage" in goal.lower():
                coverage = review.get("metrics", {}).get("project", {}).get("test_coverage", 0)
                if coverage < 80:  # Default threshold
                    issues.append(f"Coverage goal not met: {coverage}%")
        
        return len(issues) == 0, issues
    
    def run_loop(self) -> Dict[str, Any]:
        """Run the main CI/CD loop."""
        print(f"🚀 Starting CI/CD loop (max {self.max_iterations} iterations)")
        print(f"Strategy: {self.planfile.name}")
        print(f"Project: {self.project_path}")
        print("=" * 60)
        
        results = {
            "iterations": [],
            "success": False,
            "total_iterations": 0,
            "tickets_created": [],
            "final_status": "failed"
        }
        
        for self.iteration in range(1, self.max_iterations + 1):
            print(f"\n📍 Iteration {self.iteration}/{self.max_iterations}")
            print("-" * 40)
            
            iteration_result = {
                "iteration": self.iteration,
                "tests_passed": False,
                "tickets_created": [],
                "auto_fixed": False
            }
            
            # 1. Run tests
            test_result = self.run_tests()
            iteration_result["tests_passed"] = test_result.passed
            iteration_result["coverage"] = test_result.coverage
            
            if test_result.passed:
                print("✅ All tests passed!")
                
                # Check strategy completion
                strategy_complete, issues = self.check_strategy_completion()
                
                if strategy_complete:
                    print("🎉 Strategy completed successfully!")
                    results["success"] = True
                    results["final_status"] = "completed"
                    iteration_result["status"] = "completed"
                    results["iterations"].append(iteration_result)
                    break
                else:
                    print("⚠️  Strategy not complete:")
                    for issue in issues:
                        print(f"  - {issue}")
            else:
                print(f"❌ Tests failed: {len(test_result.failed_tests)} failures")
                
                # 2. Run code analysis
                metrics = self.run_code_analysis()
                
                # 3. Generate bug report
                bug_report = self.generate_bug_report(test_result, metrics)
                
                # 4. Create tickets
                ticket_urls = self.create_bug_tickets(bug_report)
                iteration_result["tickets_created"] = ticket_urls
                results["tickets_created"].extend(ticket_urls)
                
                # 5. Attempt auto-fix
                if self.auto_fix:
                    fixed = self.auto_fix_bugs(bug_report)
                    iteration_result["auto_fixed"] = fixed
                    if fixed:
                        print("✅ Auto-fix applied")
                
                iteration_result["status"] = "failed"
            
            results["iterations"].append(iteration_result)
            results["total_iterations"] = self.iteration
            
            # Small delay between iterations
            if self.iteration < self.max_iterations:
                time.sleep(2)
        
        if not results["success"]:
            print(f"\n❌ Loop completed without success after {self.max_iterations} iterations")
            results["final_status"] = "max_iterations_reached"
        
        return results
    
    def save_results(self, results: Dict[str, Any], output_path: Optional[str] = None):
        """Save results to file."""
        if not output_path:
            output_path = self.project_path / "ci-results.json"
        
        Path(output_path).write_text(json.dumps(results, indent=2))
        print(f"\n📄 Results saved to: {output_path}")


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CI/CD runner with bug-fix loop")
    parser.add_argument("--strategy", required=True, help="Strategy YAML file")
    parser.add_argument("--project", default=".", help="Project path")
    parser.add_argument("--backend", choices=["github", "jira", "gitlab"], 
                       action="append", help="PM backends to use")
    parser.add_argument("--max-iterations", type=int, default=10, 
                       help="Maximum iterations")
    parser.add_argument("--auto-fix", action="store_true", 
                       help="Enable auto-fix with LLM")
    parser.add_argument("--output", help="Output results file")
    
    args = parser.parse_args()
    
    # Initialize backends
    backends = {}
    
    if "github" in (args.backend or []):
        backends["github"] = GitHubBackend(
            repo=os.environ.get("GITHUB_REPO"),
            token=os.environ.get("GITHUB_TOKEN")
        )
    
    if "jira" in (args.backend or []):
        backends["jira"] = JiraBackend(
            base_url=os.environ.get("JIRA_URL"),
            email=os.environ.get("JIRA_EMAIL"),
            token=os.environ.get("JIRA_TOKEN"),
            project=os.environ.get("JIRA_PROJECT")
        )
    
    if "gitlab" in (args.backend or []):
        backends["gitlab"] = GitLabBackend(
            url=os.environ.get("GITLAB_URL", "https://gitlab.com"),
            token=os.environ.get("GITLAB_TOKEN"),
            project_id=os.environ.get("GITLAB_PROJECT_ID")
        )
    
    # Run CI loop
    runner = CIRunner(
        strategy_path=args.strategy,
        project_path=args.project,
        backends=backends,
        max_iterations=args.max_iterations,
        auto_fix=args.auto_fix
    )
    
    results = runner.run_loop()
    runner.save_results(results, args.output)
    
    # Exit with appropriate code
    sys.exit(0 if results["success"] else 1)


if __name__ == "__main__":
    main()
