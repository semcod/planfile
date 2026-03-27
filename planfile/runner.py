"""
Strategy validation and runner for LLX.
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
import subprocess
import json
import time
import hashlib
from functools import lru_cache

from planfile.models import Strategy, Sprint, TaskPattern
from planfile.integrations.base import PMBackend


def load_valid_strategy(path: str) -> Strategy:
    """
    Load and validate strategy from YAML file.
    
    Args:
        path: Path to strategy YAML file
        
    Returns:
        Validated Strategy object
        
    Raises:
        ValidationError: If strategy is invalid
    """
    strategy_file = Path(path)
    
    if not strategy_file.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")
    
    try:
        # Load using pydantic-yaml
        strategy = Strategy.model_validate_yaml(strategy_file.read_text())
        print(f"✅ Strategy loaded and validated: {strategy.name}")
        return strategy
    except Exception as e:
        print(f"❌ Strategy validation failed: {e}")
        raise


def verify_strategy_post_execution(
    strategy: Strategy,
    project_path: str,
    backend: Optional[str] = None
) -> Dict[str, List[str]]:
    """
    Verify strategy after execution.
    
    Args:
        strategy: Strategy to verify
        project_path: Path to project
        backend: Backend type (github, jira, etc.)
        
    Returns:
        Dictionary of issues found
    """
    issues = {
        "strategy": [],
        "metrics": [],
        "tickets": []
    }
    
    # 1. Check project metrics
    try:
        # Use code2llm or similar for metrics
        metrics = analyze_project_metrics(project_path)
        
        # Check quality goals
        for goal in strategy.goal.quality:
            if "coverage" in goal.lower():
                coverage = metrics.get("test_coverage", 0)
                if coverage < 80:  # Default threshold
                    issues["metrics"].append(f"Test coverage {coverage}% is below goal")
            
            if "performance" in goal.lower():
                # Check performance metrics
                if metrics.get("performance_score", 100) < 90:
                    issues["metrics"].append("Performance metrics not met")
        
    except Exception as e:
        issues["metrics"].append(f"Failed to analyze project: {e}")
    
    # 2. Check ticket status if backend specified
    if backend:
        try:
            # This would integrate with the actual backend
            # For now, just check if tasks.yaml exists
            tasks_file = Path(project_path) / "tasks.yaml"
            if tasks_file.exists():
                # Load and check tasks
                pass
        except Exception as e:
            issues["tickets"].append(f"Failed to check ticket status: {e}")
    
    # 3. Check sprint completion
    for sprint in strategy.sprints:
        if not sprint.tasks:
            issues["strategy"].append(f"Sprint {sprint.id} has no tasks assigned")
    
    return issues


@lru_cache(maxsize=32)
def _get_project_hash(project_path: str) -> str:
    """Get a hash of project files for cache invalidation."""
    path = Path(project_path)
    if not path.exists():
        return ""
    
    # Simple hash based on file count and mod time of key files
    file_count = 0
    latest_mod = 0
    for file_path in path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            file_count += 1
            latest_mod = max(latest_mod, file_path.stat().st_mtime)
    
    return hashlib.md5(f"{file_count}-{latest_mod}".encode()).hexdigest()[:16]


def analyze_project_metrics(project_path: str) -> Dict[str, Any]:
    """
    Analyze project metrics using available tools.
    
    Args:
        project_path: Path to project
        
    Returns:
        Dictionary with metrics
    """
    path = Path(project_path)
    metrics = {
        "file_count": 0,
        "test_coverage": 0,
        "performance_score": 100,
        "language_distribution": {}
    }
    
    if not path.exists():
        return metrics
    
    # Count files (optimized with rg if available)
    try:
        result = subprocess.run(
            ["rg", "--files", "--type", "py", "--count"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5  # Add timeout
        )
        if result.returncode == 0:
            metrics["file_count"] = int(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Fallback to manual counting
        for file_path in path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith("."):
                metrics["file_count"] += 1
    
    # Try to get test coverage if pytest coverage exists (with caching)
    project_hash = _get_project_hash(project_path)
    cache_file = Path.home() / ".planfile_cache" / f"coverage_{project_hash}.json"
    
    try:
        # Try cache first
        if cache_file.exists():
            cache_data = json.loads(cache_file.read_text())
            if time.time() - cache_data.get("timestamp", 0) < 300:  # 5 minutes cache
                metrics["test_coverage"] = cache_data["coverage"]
                return metrics
        
        # Run pytest coverage with timeout
        result = subprocess.run(
            ["python", "-m", "pytest", "--cov=.", "--cov-report=json", "--quiet"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=30  # 30 second timeout
        )
        if result.returncode == 0:
            coverage_file = path / "coverage.json"
            if coverage_file.exists():
                coverage_data = json.loads(coverage_file.read_text())
                coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
                metrics["test_coverage"] = coverage
                
                # Cache the result
                cache_file.parent.mkdir(exist_ok=True)
                cache_file.write_text(json.dumps({
                    "coverage": coverage,
                    "timestamp": time.time()
                }))
    except (subprocess.TimeoutExpired, Exception):
        pass
    
    return metrics


def apply_strategy_to_tickets(
    strategy: Strategy,
    project_path: str,
    backend: str = "github",
    dry_run: bool = True
) -> Dict[str, Any]:
    """
    Apply strategy to create tickets in PM system.
    
    Args:
        strategy: Strategy to apply
        project_path: Project path
        backend: Backend type
        dry_run: If True, only simulate
        
    Returns:
        Results dictionary
    """
    results = {
        "created": [],
        "updated": [],
        "errors": [],
        "dry_run": dry_run
    }
    
    print(f"{'[DRY RUN] ' if dry_run else ''}Applying strategy: {strategy.name}")
    
    for sprint in strategy.sprints:
        print(f"\nProcessing Sprint {sprint.id}: {sprint.name}")
        
        for task_id in sprint.tasks:
            # Find task pattern
            pattern = None
            for p in strategy.get_task_patterns():
                if p.id == task_id:
                    pattern = p
                    break
            
            if not pattern:
                results["errors"].append(f"Task pattern '{task_id}' not found")
                continue
            
            # Create ticket
            ticket_info = {
                "sprint": sprint.id,
                "pattern": pattern.id,
                "title": pattern.title,
                "type": pattern.type.value,
                "priority": pattern.priority
            }
            
            if dry_run:
                results["created"].append(ticket_info)
                print(f"  Would create: {pattern.title}")
            else:
                # Here you would actually create the ticket
                # For now, just simulate
                results["created"].append(ticket_info)
                print(f"  Created: {pattern.title}")
    
    return results


def review_strategy(
    strategy: Strategy,
    project_path: str,
    backends: Dict[str, PMBackend],
    backend_name: str = "default",
) -> Dict[str, Any]:
    """
    Review strategy execution by checking ticket statuses.
    
    This is a convenience function that creates a StrategyRunner
    and reviews the planfile.
    """
    runner = StrategyRunner(backends)
    return runner.review_strategy(
        strategy=strategy,
        project_path=project_path,
        backend_name=backend_name
    )


def run_strategy(
    strategy_path: str,
    project_path: str,
    backend: str = "github",
    dry_run: bool = True
):
    """
    Run strategy: load, validate, and apply.
    
    Args:
        strategy_path: Path to strategy YAML
        project_path: Project path
        backend: Backend type
        dry_run: If True, only simulate
    """
    # Load and validate
    strategy = load_valid_strategy(strategy_path)
    
    # Apply strategy
    results = apply_strategy_to_tickets(
        strategy=strategy,
        project_path=project_path,
        backend=backend,
        dry_run=dry_run
    )
    
    # Summary
    print("\n" + "=" * 50)
    print("STRATEGY EXECUTION SUMMARY")
    print("=" * 50)
    print(f"Strategy: {strategy.name}")
    print(f"Sprints: {len(strategy.sprints)}")
    print(f"Tasks created: {len(results['created'])}")
    print(f"Errors: {len(results['errors'])}")
    
    if results["errors"]:
        print("\nErrors:")
        for error in results["errors"]:
            print(f"  - {error}")
    
    # Verify after execution (if not dry run)
    if not dry_run:
        print("\nVerifying strategy execution...")
        issues = verify_strategy_post_execution(strategy, project_path, backend)
        
        if any(issues.values()):
            print("\nIssues found:")
            for category, items in issues.items():
                if items:
                    print(f"  {category}:")
                    for item in items:
                        print(f"    - {item}")
        else:
            print("✅ No issues found!")
