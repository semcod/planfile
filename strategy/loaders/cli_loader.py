import json
from pathlib import Path
from typing import Dict, Any, Union

from ..models import Strategy, TaskPattern


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
    data = strategy.model_dump()
    save_to_json(data, file_path)


def export_results_to_markdown(results: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Export strategy results to Markdown file.
    
    Args:
        results: Results from apply_strategy or review_strategy
        file_path: Path to save Markdown file
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    md_content = []
    
    # Header
    md_content.append(f"# Strategy Results: {results.get('strategy', 'Unknown')}")
    md_content.append(f"**Applied:** {results.get('applied_at', 'Unknown')}")
    md_content.append(f"**Backend:** {results.get('backend', 'Unknown')}")
    md_content.append("")
    
    # Summary
    if "summary" in results:
        summary = results["summary"]
        md_content.append("## Summary")
        md_content.append(f"- Created: {summary.get('created', 0)}")
        md_content.append(f"- Updated: {summary.get('updated', 0)}")
        md_content.append(f"- Errors: {summary.get('errors', 0)}")
        md_content.append("")
    
    # Tickets
    if "tickets" in results and results["tickets"]:
        md_content.append("## Tickets")
        md_content.append("| Sprint | Task | ID | URL |")
        md_content.append("|--------|------|----|----|")
        
        for key, ticket in results["tickets"].items():
            parts = key.split("-")
            sprint_id = parts[1] if len(parts) > 1 else "N/A"
            task_id = parts[3] if len(parts) > 3 else "N/A"
            
            url = f"[{ticket.id}]({ticket.url})" if ticket.url else ticket.id
            md_content.append(f"| {sprint_id} | {task_id} | {ticket.id} | {url} |")
        md_content.append("")
    
    # Sprint details
    if "sprints" in results:
        md_content.append("## Sprint Details")
        
        for sprint_id, sprint_data in results["sprints"].items():
            md_content.append(f"### Sprint {sprint_id}: {sprint_data.get('name', 'Unknown')}")
            md_content.append(f"**Status:** {sprint_data.get('status', 'Unknown')}")
            
            if "objectives" in sprint_data:
                md_content.append("**Objectives:**")
                for obj in sprint_data["objectives"]:
                    md_content.append(f"- {obj}")
            
            if "tickets" in sprint_data:
                md_content.append("**Tickets:**")
                for ticket_id, ticket_info in sprint_data["tickets"].items():
                    status = ticket_info.get("status", "Unknown")
                    assignee = ticket_info.get("assignee", "Unassigned")
                    md_content.append(f"- #{ticket_id}: {status} ({assignee})")
            
            md_content.append("")
    
    # Metrics
    if "metrics" in results:
        md_content.append("## Metrics")
        
        metrics = results["metrics"]
        if "progress" in metrics:
            progress = metrics["progress"]
            md_content.append("### Progress")
            md_content.append(f"- Completion Rate: {progress.get('completion_rate', 0):.1%}")
            md_content.append(f"- In Progress Rate: {progress.get('in_progress_rate', 0):.1%}")
            md_content.append(f"- Blocked Rate: {progress.get('blocked_rate', 0):.1%}")
        
        if "project" in metrics:
            project = metrics["project"]
            md_content.append("### Project")
            md_content.append(f"- Path: {project.get('path', 'Unknown')}")
            md_content.append(f"- Files: {project.get('file_count', 0)}")
            
            if "language_distribution" in project:
                md_content.append("**Languages:**")
                for lang, count in list(project["language_distribution"].items())[:5]:
                    md_content.append(f"  - {lang}: {count}")
    
    # Write to file
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
