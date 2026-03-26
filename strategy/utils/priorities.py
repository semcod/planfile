from typing import Optional
from ..models import TaskType


def calculate_task_priority(
    base_priority: Optional[str],
    task_type: TaskType,
    sprint_id: int,
    weight_factors: Optional[dict] = None
) -> str:
    """
    Calculate task priority based on type, sprint, and base priority.
    
    Args:
        base_priority: Base priority from task pattern
        task_type: Type of the task
        sprint_id: Sprint number
        weight_factors: Optional custom weight factors
    
    Returns:
        Calculated priority string
    """
    # Default weight factors
    default_weights = {
        "bug": {"boost": 2, "base": "high"},
        "feature": {"boost": 0, "base": "medium"},
        "tech_debt": {"boost": -1, "base": "low"},
        "chore": {"boost": -2, "base": "low"},
        "documentation": {"boost": -1, "base": "low"}
    }
    
    weights = weight_factors or default_weights
    
    # Get type-specific weight
    type_weight = weights.get(task_type.value, {"boost": 0, "base": "medium"})
    
    # Priority levels
    priority_levels = ["lowest", "low", "medium", "high", "highest"]
    
    # Start with base priority
    if base_priority and base_priority in priority_levels:
        base_index = priority_levels.index(base_priority)
    else:
        base_index = priority_levels.index(type_weight["base"])
    
    # Apply sprint-based boost (earlier sprints get higher priority)
    sprint_boost = max(0, 5 - sprint_id) // 2
    
    # Calculate final priority index
    final_index = base_index + type_weight["boost"] + sprint_boost
    final_index = max(0, min(len(priority_levels) - 1, final_index))
    
    return priority_levels[final_index]


def map_priority_to_system(
    priority: str,
    system: str = "github"
) -> str:
    """
    Map generic priority to system-specific priority.
    
    Args:
        priority: Generic priority (lowest, low, medium, high, highest)
        system: Target system (github, jira, gitlab)
    
    Returns:
        System-specific priority
    """
    if system == "github":
        # GitHub uses labels
        return priority
    
    elif system == "jira":
        # Jira priority names
        jira_map = {
            "lowest": "Lowest",
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "highest": "Highest"
        }
        return jira_map.get(priority, "Medium")
    
    elif system == "gitlab":
        # GitLab uses labels with prefix
        return f"priority::{priority}"
    
    else:
        # Default to generic priority
        return priority


def get_priority_color(priority: str) -> str:
    """
    Get color code for priority (for UI display).
    
    Args:
        priority: Priority string
    
    Returns:
        Hex color code
    """
    colors = {
        "lowest": "#6B7280",  # Gray
        "low": "#3B82F6",     # Blue
        "medium": "#F59E0B",  # Amber
        "high": "#EF4444",    # Red
        "highest": "#DC2626"  # Dark Red
    }
    return colors.get(priority, "#6B7280")
