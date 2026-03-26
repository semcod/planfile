import json
from pathlib import Path
from typing import Dict, Any, Union, List

from planfile.models import Strategy, TaskPattern


def load_from_json(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load JSON file and return as dictionary.
    
    Args:
        file_path: Path to JSON file
    
    Returns:
        Dictionary with JSON content
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_to_json(data: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Save dictionary to JSON file.
    
    Args:
        data: Dictionary to save
        file_path: Path to save JSON file
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def load_strategy_from_json(file_path: Union[str, Path]) -> Strategy:
    """
    Load strategy from JSON file.
    
    Args:
        file_path: Path to strategy JSON file
    
    Returns:
        Strategy instance
    """
    data = load_from_json(file_path)
    return Strategy(**data)


def save_strategy_to_json(strategy: Strategy, file_path: Union[str, Path]) -> None:
    """
    Save strategy to JSON file.
    
    Args:
        strategy: Strategy instance
        file_path: Path to save JSON file
    """
    data = planfile.model_dump()
    save_to_json(data, file_path)


def _md_header(results: Dict[str, Any]) -> List[str]:
    """Generate markdown header section."""
    return [
        f"# Strategy Results: {results.get('strategy', 'Unknown')}",
        f"**Applied:** {results.get('applied_at', 'Unknown')}",
        f"**Backend:** {results.get('backend', 'Unknown')}",
        ""
    ]


def _md_summary(results: Dict[str, Any]) -> List[str]:
    """Generate markdown summary section."""
    if "summary" not in results:
        return []
    
    summary = results["summary"]
    return [
        "## Summary",
        f"- Created: {summary.get('created', 0)}",
        f"- Updated: {summary.get('updated', 0)}",
        f"- Errors: {summary.get('errors', 0)}",
        ""
    ]


def _md_tasks(results: Dict[str, Any]) -> List[str]:
    """Generate markdown tickets section."""
    if "tickets" not in results or not results["tickets"]:
        return []
    
    md = [
        "## Tickets",
        "| Sprint | Task | ID | URL |",
        "|--------|------|----|----|"
    ]
    
    for key, ticket in results["tickets"].items():
        parts = key.split("-")
        sprint_id = parts[1] if len(parts) > 1 else "N/A"
        task_id = parts[3] if len(parts) > 3 else "N/A"
        
        url = f"[{ticket.id}]({ticket.url})" if ticket.url else ticket.id
        md.append(f"| {sprint_id} | {task_id} | {ticket.id} | {url} |")
    
    md.append("")
    return md


def _md_sprints(results: Dict[str, Any]) -> List[str]:
    """Generate markdown sprint details section."""
    if "sprints" not in results:
        return []
    
    md = ["## Sprint Details"]
    
    for sprint_id, sprint_data in results["sprints"].items():
        md.append(f"### Sprint {sprint_id}: {sprint_data.get('name', 'Unknown')}")
        md.append(f"**Status:** {sprint_data.get('status', 'Unknown')}")
        
        if "objectives" in sprint_data:
            md.append("**Objectives:**")
            for obj in sprint_data["objectives"]:
                md.append(f"- {obj}")
        
        if "tickets" in sprint_data:
            md.append("**Tickets:**")
            for ticket_id, ticket_info in sprint_data["tickets"].items():
                status = ticket_info.get("status", "Unknown")
                assignee = ticket_info.get("assignee", "Unassigned")
                md.append(f"- #{ticket_id}: {status} ({assignee})")
        
        md.append("")
    
    return md


def _md_metrics(results: Dict[str, Any]) -> List[str]:
    """Generate markdown metrics section."""
    if "metrics" not in results:
        return []
    
    md = ["## Metrics"]
    metrics = results["metrics"]
    
    if "progress" in metrics:
        progress = metrics["progress"]
        md.append("### Progress")
        md.append(f"- Completion Rate: {progress.get('completion_rate', 0):.1%}")
        md.append(f"- In Progress Rate: {progress.get('in_progress_rate', 0):.1%}")
        md.append(f"- Blocked Rate: {progress.get('blocked_rate', 0):.1%}")
    
    if "project" in metrics:
        project = metrics["project"]
        md.append("### Project")
        md.append(f"- Path: {project.get('path', 'Unknown')}")
        md.append(f"- Files: {project.get('file_count', 0)}")
        
        if "language_distribution" in project:
            md.append("**Languages:**")
            for lang, count in list(project["language_distribution"].items())[:5]:
                md.append(f"  - {lang}: {count}")
    
    return md


def export_results_to_markdown(results: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Export strategy results to Markdown file.
    
    Args:
        results: Results from apply_strategy or review_strategy
        file_path: Path to save Markdown file
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build markdown content
    md_content = []
    md_content.extend(_md_header(results))
    md_content.extend(_md_summary(results))
    md_content.extend(_md_tasks(results))
    md_content.extend(_md_sprints(results))
    md_content.extend(_md_metrics(results))
    
    # Write to file
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
