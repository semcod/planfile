from typing import Dict, Any, Optional
from pathlib import Path
import os
import subprocess
import json


def analyze_project_metrics(project_path: str) -> Dict[str, Any]:
    """
    Analyze project metrics for strategy review.
    
    Args:
        project_path: Path to the project directory
    
    Returns:
        Dictionary with project metrics
    """
    path = Path(project_path)
    metrics = {
        "path": str(path.absolute()),
        "exists": path.exists(),
        "is_git_repo": False,
        "file_count": 0,
        "language_distribution": {},
        "last_commit": None,
        "branch_count": 0,
        "total_commits": 0
    }
    
    if not path.exists():
        return metrics
    
    # Check if it's a git repository
    git_path = path / ".git"
    if git_path.exists():
        metrics["is_git_repo"] = True
        
        try:
            # Get git metrics
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["current_branch"] = result.stdout.strip()
            
            # Get last commit date
            result = subprocess.run(
                ["git", "-C", str(path), "log", "-1", "--format=%ci"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["last_commit"] = result.stdout.strip()
            
            # Get commit count
            result = subprocess.run(
                ["git", "-C", str(path), "rev-list", "--count", "HEAD"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["total_commits"] = int(result.stdout.strip())
            
            # Get branch count
            result = subprocess.run(
                ["git", "-C", str(path), "branch", "-a"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                metrics["branch_count"] = len([b for b in result.stdout.split("\n") if b.strip()])
                
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
    
    # Count files by extension
    file_extensions = {}
    for file_path in path.rglob("*"):
        if file_path.is_file() and not file_path.name.startswith("."):
            metrics["file_count"] += 1
            ext = file_path.suffix.lower()
            if ext:
                file_extensions[ext] = file_extensions.get(ext, 0) + 1
    
    # Map extensions to languages
    language_map = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".jsx": "React",
        ".tsx": "React/TypeScript",
        ".java": "Java",
        ".go": "Go",
        ".rs": "Rust",
        ".cpp": "C++",
        ".c": "C",
        ".cs": "C#",
        ".php": "PHP",
        ".rb": "Ruby",
        ".swift": "Swift",
        ".kt": "Kotlin",
        ".scala": "Scala",
        ".sh": "Shell",
        ".sql": "SQL",
        ".html": "HTML",
        ".css": "CSS",
        ".scss": "Sass",
        ".less": "Less",
        ".yaml": "YAML",
        ".yml": "YAML",
        ".json": "JSON",
        ".xml": "XML",
        ".md": "Markdown",
        ".txt": "Text",
    }
    
    for ext, count in file_extensions.items():
        lang = language_map.get(ext, ext)
        metrics["language_distribution"][lang] = metrics["language_distribution"].get(lang, 0) + count
    
    # Sort languages by count
    metrics["language_distribution"] = dict(
        sorted(metrics["language_distribution"].items(), key=lambda x: x[1], reverse=True)
    )
    
    # Check for common project files
    common_files = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        "CHANGELOG.md",
        ".gitignore",
    ]
    
    metrics["project_files"] = {}
    for file_name in common_files:
        file_path = path / file_name
        metrics["project_files"][file_name] = file_path.exists()
    
    return metrics


def calculate_strategy_health(strategy_results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate health metrics for a strategy execution.
    
    Args:
        strategy_results: Results from review_strategy
    
    Returns:
        Health metrics
    """
    health = {
        "overall_score": 0,
        "completion_rate": 0,
        "blocked_issues": 0,
        "stalled_sprints": 0,
        "recommendations": []
    }
    
    summary = strategy_results.get("summary", {})
    total = summary.get("total_tickets", 0)
    
    if total > 0:
        completed = summary.get("completed", 0)
        health["completion_rate"] = completed / total
        health["blocked_issues"] = summary.get("blocked", 0)
        
        # Calculate overall score (0-100)
        health["overall_score"] = int(health["completion_rate"] * 100)
        
        # Deduct points for blocked issues
        health["overall_score"] -= health["blocked_issues"] * 10
        health["overall_score"] = max(0, health["overall_score"])
    
    # Check for stalled sprints
    sprints = strategy_results.get("sprints", {})
    for sprint_data in sprints.values():
        if sprint_data.get("status") == "not_started":
            health["stalled_sprints"] += 1
    
    # Generate recommendations
    if health["completion_rate"] < 0.5:
        health["recommendations"].append("Consider reviewing sprint capacity and task estimates")
    
    if health["blocked_issues"] > 0:
        health["recommendations"].append(f"Address {health['blocked_issues']} blocked issue(s)")
    
    if health["stalled_sprints"] > 0:
        health["recommendations"].append(f"{health['stalled_sprints']} sprint(s) haven't started - review dependencies")
    
    return health
