import yaml
from pathlib import Path
from typing import Dict, Any, Union
from pydantic import ValidationError

from planfile.models import Strategy, Sprint, TaskPattern, TaskType, ModelHints, ModelTier, QualityGate


def load_yaml(file_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Load YAML file and return as dictionary.
    
    Args:
        file_path: Path to YAML file
    
    Returns:
        Dictionary with YAML content
    
    Raises:
        FileNotFoundError: If file doesn't exist
        yaml.YAMLError: If YAML is invalid
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        try:
            content = yaml.safe_load(f)
            return content or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in {path}: {e}")


def save_yaml(data: Dict[str, Any], file_path: Union[str, Path]) -> None:
    """
    Save dictionary to YAML file.
    
    Args:
        data: Dictionary to save
        file_path: Path to save YAML file
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)


def load_strategy_yaml(file_path: Union[str, Path]) -> Strategy:
    """
    Load strategy from YAML file.
    
    Args:
        file_path: Path to strategy YAML file
    
    Returns:
        Strategy instance
    
    Raises:
        ValidationError: If strategy is invalid
    """
    data = load_yaml(file_path)
    
    # Convert task patterns
    if "tasks" in data:
        for category, patterns in data["tasks"].items():
            for i, pattern in enumerate(patterns):
                # Convert model_hints if present
                if "model_hints" in pattern:
                    pattern["model_hints"] = ModelHints(**pattern["model_hints"])
                
                # Convert type to enum
                if "type" in pattern:
                    pattern["type"] = TaskType(pattern["type"])
    
    # Convert sprints
    if "sprints" in data:
        for i, sprint in enumerate(data["sprints"]):
            # Ensure tasks is a list
            if "tasks" not in sprint:
                sprint["tasks"] = []
    
    # Convert quality gates
    if "quality_gates" in data:
        for i, gate in enumerate(data["quality_gates"]):
            data["quality_gates"][i] = QualityGate(**gate)
    
    try:
        return Strategy.load_flexible(data)
    except Exception as e:
        # Re-raise with more context
        if hasattr(e, 'errors') and callable(e.errors):
            # Pydantic validation error
            error_msg = f"Invalid strategy in {file_path}:\n"
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error['loc'])
                error_msg += f"  {loc}: {error['msg']}\n"
            raise ValueError(error_msg)
        else:
            raise ValueError(f"Invalid strategy in {file_path}: {e}")


def save_strategy_yaml(strategy: Union[Strategy, Dict], file_path: Union[str, Path]) -> None:
    """
    Save strategy to YAML file.
    
    Args:
        strategy: Strategy instance or dictionary
        file_path: Path to save YAML file
    """
    if isinstance(strategy, dict):
        data = strategy
    else:
        data = strategy.model_dump()
    
    # Convert enums to strings
    if "tasks" in data:
        for category, patterns in data["tasks"].items():
            for pattern in patterns:
                if "type" in pattern:
                    pattern["type"] = pattern["type"].value
    
    save_yaml(data, file_path)


def load_tasks_yaml(file_path: Union[str, Path]) -> Dict[str, list[TaskPattern]]:
    """
    Load task patterns from YAML file.
    
    Args:
        file_path: Path to tasks YAML file
    
    Returns:
        Dictionary of task patterns by category
    """
    data = load_yaml(file_path)
    
    tasks = {}
    for category, patterns in data.items():
        tasks[category] = []
        for pattern in patterns:
            # Convert model_hints if present
            if "model_hints" in pattern:
                pattern["model_hints"] = ModelHints(**pattern["model_hints"])
            
            # Convert type to enum
            if "type" in pattern:
                pattern["type"] = TaskType(pattern["type"])
            
            tasks[category].append(TaskPattern(**pattern))
    
    return tasks


def merge_strategy_with_tasks(
    strategy: Strategy,
    tasks_file: Union[str, Path]
) -> Strategy:
    """
    Merge additional task patterns into a planfile.
    
    Args:
        strategy: Base strategy
        tasks_file: Path to additional tasks YAML file
    
    Returns:
        Strategy with merged tasks
    """
    additional_tasks = load_tasks_yaml(tasks_file)
    
    # Merge tasks
    for category, patterns in additional_tasks.items():
        if category not in planfile.tasks:
            planfile.tasks[category] = []
        planfile.tasks[category].extend(patterns)
    
    return strategy


def _check_required_keys(data: dict, issues: list[str]) -> None:
    """Check required top-level fields."""
    required_fields = ["name", "project_type", "domain", "goal"]
    for field in required_fields:
        if field not in data:
            issues.append(f"Missing required field: {field}")


def _validate_sprints(data: dict, issues: list[str]) -> None:
    """Validate sprint section."""
    if "sprints" not in data:
        return
    
    sprint_ids = set()
    for i, sprint in enumerate(data["sprints"]):
        if "id" not in sprint:
            issues.append(f"Sprint {i} missing required field: id")
        else:
            if sprint["id"] in sprint_ids:
                issues.append(f"Duplicate sprint ID: {sprint['id']}")
            sprint_ids.add(sprint["id"])
        
        if "name" not in sprint:
            issues.append(f"Sprint {i} missing required field: name")


def _validate_gates(data: dict, issues: list[str]) -> None:
    """Validate quality gates section."""
    if "quality_gates" not in data:
        return
    
    for i, gate in enumerate(data["quality_gates"]):
        if "metric" not in gate:
            issues.append(f"Quality gate {i} missing required field: metric")
        if "condition" not in gate:
            issues.append(f"Quality gate {i} missing required field: condition")
        if "threshold" not in gate:
            issues.append(f"Quality gate {i} missing required field: threshold")


def _validate_task_patterns(data: dict, issues: list[str]) -> None:
    """Validate task patterns section."""
    if "tasks" not in data:
        return
    
    for category, patterns in data["tasks"].items():
        for i, pattern in enumerate(patterns):
            if "id" not in pattern:
                issues.append(f"Task pattern {category}[{i}] missing required field: id")
            if "title" not in pattern:
                issues.append(f"Task pattern {category}[{i}] missing required field: title")
            if "description" not in pattern:
                issues.append(f"Task pattern {category}[{i}] missing required field: description")


def validate_strategy_schema(file_path: Union[str, Path]) -> list[str]:
    """
    Validate strategy YAML file and return list of issues.
    
    Args:
        file_path: Path to strategy YAML file
    
    Returns:
        List of validation issues (empty if valid)
    """
    issues = []
    
    try:
        data = load_yaml(file_path)
    except Exception as e:
        return [f"Failed to load YAML: {e}"]
    
    # Check required fields
    _check_required_keys(data, issues)
    
    # Validate sprints
    _validate_sprints(data, issues)
    
    # Validate quality gates
    _validate_gates(data, issues)
    
    # Validate task patterns
    _validate_task_patterns(data, issues)
    
    # Try to validate with Pydantic
    if not issues:
        try:
            load_strategy_yaml(file_path)
        except ValidationError as e:
            issues.extend(str(e).split("\n"))
    
    return issues
