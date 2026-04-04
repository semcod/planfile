"""Strategy models - sprints, tasks, goals, quality gates."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .base import (
    DEFAULT_SPRINT_LENGTH_DAYS,
    DAYS_PER_WEEK,
    INITIAL_SPRINT_ID,
    TaskType,
)


class ModelHints(BaseModel):
    """AI model hints for different phases of task execution."""
    design: Optional["ModelTier"] = None
    implementation: Optional["ModelTier"] = None
    review: Optional["ModelTier"] = None
    triage: Optional["ModelTier"] = None

    @field_validator('*', mode='before')
    @classmethod
    def convert_str_to_tier(cls, v) -> Any:
        if isinstance(v, str):
            from .base import ModelTier
            if v not in ModelTier.__members__:
                if v == "free":
                    return ModelTier.cheap
        return v


class Task(BaseModel):
    """A task in a sprint - simplified and directly embedded."""
    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Task description")
    type: TaskType = Field(TaskType.feature, description="Type of task")
    priority: str | None = Field("medium", description="Priority: low, medium, high")
    model_hints: dict[str, str] | None = Field(default_factory=dict, description="Model preferences")
    estimate: str | None = Field(None, description="Estimate (e.g., '3d', '1w')")
    tags: list[str] = Field(default_factory=list, description="Tags for organization")

    @field_validator('model_hints', mode='before')
    @classmethod
    def normalize_model_hints(cls, v) -> dict[str, str] | None:
        if isinstance(v, str):
            return {"implementation": v}
        elif isinstance(v, dict):
            return v
        return {}


# Backward compatibility alias
TaskPattern = Task


class Sprint(BaseModel):
    """A sprint in the planfile."""
    id: int | str = Field(..., description="Sprint number or ID")
    name: str = Field(..., description="Sprint name")
    objectives: list[str] = Field(default_factory=list, description="Sprint objectives")
    tasks: list[Task] = Field(default_factory=list, description="Tasks in this sprint")
    length_days: int | None = Field(DEFAULT_SPRINT_LENGTH_DAYS, description="Sprint length in days")
    duration: str | None = Field(None, description="Sprint duration (e.g., '2 weeks')")
    start_date: str | None = Field(None, description="Start date (ISO format)")

    @field_validator('tasks', mode='before')
    @classmethod
    def convert_tasks(cls, v) -> list[Task]:
        if isinstance(v, list):
            tasks = []
            for item in v:
                if isinstance(item, dict):
                    if 'task_patterns' in item:
                        continue
                    elif 'name' in item:
                        tasks.append(Task(**item))
                    else:
                        tasks.append(Task(
                            name=item.get('title', 'Unnamed Task'),
                            description=item.get('description', ''),
                            type=item.get('type', TaskType.feature),
                            priority=item.get('priority', 'medium'),
                            model_hints=item.get('model_hints', {})
                        ))
                elif isinstance(item, str):
                    # Allow string task IDs for backward compat
                    tasks.append(item)
                elif isinstance(item, Task):
                    tasks.append(item)
            return tasks
        return v


class QualityGate(BaseModel):
    """Quality gate definition."""
    name: str = Field(..., description="Gate name")
    description: str | None = Field(None, description="Gate description")
    criteria: str | list[str] = Field(..., description="Criteria to pass the gate")
    required: bool = Field(True, description="Whether this gate is required")

    @field_validator('criteria', mode='before')
    @classmethod
    def normalize_criteria(cls, v):
        if isinstance(v, str):
            return [v]
        return v


class Goal(BaseModel):
    """Project goal definition."""
    short: str = Field(..., description="Short goal description")
    quality: list[str] = Field(default_factory=list, description="Quality goals")
    delivery: list[str] = Field(default_factory=list, description="Delivery goals")
    metrics: list[str] = Field(default_factory=list, description="Metric goals")


class Strategy(BaseModel):
    """Main strategy configuration - simplified and more flexible."""
    name: str = Field(..., description="Strategy name")
    version: str | None = Field(None, description="Strategy version")
    project_type: str | None = Field("software", description="Type of project")
    domain: str | None = Field("software", description="Business domain")

    # Goal can be string or Goal object
    goal: str | None = Field(None, description="Main goal of this strategy")
    description: str | None = Field(None, description="Detailed description")

    # Sprints - the main structure
    sprints: list[Sprint] = Field(default_factory=list, description="Sprints in this strategy")

    # Task patterns (v1 compat)
    tasks: dict[str, Any] = Field(
        default_factory=dict,
        description="Task patterns by category (v1 compat)"
    )

    # Quality gates
    quality_gates: list[QualityGate] = Field(default_factory=list, description="Quality gates")

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_task_patterns(self, category: str = None) -> list[Task]:
        """Get all tasks from all sprints (or patterns by category for v1 compat)."""
        if category and isinstance(self.tasks, dict):
            return self.tasks.get(category, [])
        all_tasks = []
        for sprint in self.sprints:
            all_tasks.extend(sprint.tasks)
        return all_tasks

    def get_sprint(self, sprint_id: int) -> Sprint | None:
        """Get sprint by ID."""
        for sprint in self.sprints:
            if sprint.id == sprint_id:
                return sprint
        return None

    @field_validator('sprints')
    def validate_sprint_ids(cls, v):
        """Ensure sprint IDs are unique."""
        ids = [sprint.id for sprint in v if isinstance(sprint, Sprint)]
        if len(ids) != len(set(ids)):
            raise ValueError("Sprint IDs must be unique")
        return v

    def compare(self, other: 'Strategy') -> dict[str, Any]:
        """Compare with another strategy and return differences."""
        from .base import JSON_INDENT
        comparison = {
            'common_elements': [],
            'differences': [],
            'only_in_self': [],
            'only_in_other': [],
            'similarity_score': 0.0
        }

        if self.name == other.name:
            comparison['common_elements'].append(f"Name: {self.name}")
        else:
            comparison['differences'].append({
                'field': 'name', 'self': self.name, 'other': other.name
            })

        self_goal = self.goal.short if isinstance(self.goal, Goal) else str(self.goal)
        other_goal = other.goal.short if isinstance(other.goal, Goal) else str(other.goal)

        if self_goal == other_goal:
            comparison['common_elements'].append(f"Goal: {self_goal}")
        else:
            comparison['differences'].append({
                'field': 'goal', 'self': self_goal, 'other': other_goal
            })

        self_sprint_ids = {s.id for s in self.sprints}
        other_sprint_ids = {s.id for s in other.sprints}

        comparison['common_elements'].extend([
            f"Sprint {sid}" for sid in self_sprint_ids & other_sprint_ids
        ])
        comparison['only_in_self'].extend([
            f"Sprint {sid}" for sid in self_sprint_ids - other_sprint_ids
        ])
        comparison['only_in_other'].extend([
            f"Sprint {sid}" for sid in other_sprint_ids - self_sprint_ids
        ])

        total_elements = 2 + len(self_sprint_ids) + len(other_sprint_ids)
        common_elements = 2 + len(self_sprint_ids & other_sprint_ids)
        comparison['similarity_score'] = common_elements / total_elements if total_elements > 0 else 0

        return comparison

    def merge(self, others: list['Strategy'], name: str = None) -> 'Strategy':
        """Merge with other strategies to create a combined strategy."""
        if not others:
            return self

        from .base import INITIAL_SPRINT_ID
        merged_data = self.model_dump()

        if name:
            merged_data['name'] = name
        else:
            all_names = [self.name] + [s.name for s in others]
            merged_data['name'] = f"Merged: {' + '.join(all_names)}"

        all_sprints = [merged_data.get('sprints', [])]
        for other in others:
            all_sprints.append(other.model_dump().get('sprints', []))

        merged_sprints = []
        sprint_id = INITIAL_SPRINT_ID
        for sprints in all_sprints:
            for sprint in sprints:
                sprint_copy = sprint.copy()
                sprint_copy['id'] = sprint_id
                merged_sprints.append(Sprint(**sprint_copy))
                sprint_id += 1

        merged_data['sprints'] = merged_sprints

        all_gates = [merged_data.get('quality_gates', [])]
        for other in others:
            all_gates.append(other.model_dump().get('quality_gates', []))

        merged_gates = []
        gate_names = set()
        for gates in all_gates:
            for gate in gates:
                gate_name = gate.get('name', 'Unnamed')
                if gate_name not in gate_names:
                    merged_gates.append(QualityGate(**gate))
                    gate_names.add(gate_name)

        merged_data['quality_gates'] = merged_gates

        merged_metadata = merged_data.get('metadata', {})
        for other in others:
            other_metadata = other.model_dump().get('metadata', {})
            merged_metadata.update(other_metadata)

        merged_data['metadata'] = merged_metadata

        return Strategy(**merged_data)

    def export(self, format: str = 'yaml') -> str:
        """Export strategy to specified format."""
        import json
        import yaml
        from .base import JSON_INDENT

        if format.lower() == 'yaml':
            try:
                return yaml.safe_dump(self.model_dump(), default_flow_style=False, sort_keys=False)
            except Exception as e:
                print(f"Warning: safe_dump failed in export, using regular dump: {e}")
                return yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)
        elif format.lower() == 'json':
            return json.dumps(self.model_dump(), indent=JSON_INDENT, default=str)
        elif format.lower() == 'dict':
            return self.model_dump()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_stats(self) -> dict[str, Any]:
        """Get strategy statistics."""
        from .base import DAYS_PER_WEEK
        stats = {
            'total_sprints': len(self.sprints),
            'total_tasks': sum(len(sprint.tasks) for sprint in self.sprints),
            'total_quality_gates': len(self.quality_gates),
            'project_type': self.project_type,
            'domain': self.domain,
            'version': self.version
        }

        task_types = {}
        for sprint in self.sprints:
            for task in sprint.tasks:
                if isinstance(task, Task):
                    task_type = task.type.value
                    task_types[task_type] = task_types.get(task_type, 0) + 1
        stats['task_types'] = task_types

        durations = []
        for sprint in self.sprints:
            if hasattr(sprint, 'length_days') and sprint.length_days:
                durations.append(sprint.length_days)
            elif hasattr(sprint, 'duration') and sprint.duration:
                duration_str = sprint.duration.lower()
                if 'week' in duration_str:
                    try:
                        weeks = int(duration_str.split()[0])
                        durations.append(weeks * DAYS_PER_WEEK)
                    except (ValueError, IndexError):
                        pass
                elif 'day' in duration_str:
                    try:
                        days = int(duration_str.split()[0])
                        durations.append(days)
                    except (ValueError, IndexError):
                        pass

        if durations:
            stats['total_duration_days'] = sum(durations)
            stats['avg_duration_days'] = sum(durations) / len(durations)

        return stats

    def to_yaml(self) -> str:
        """Export to YAML with clean formatting."""
        import yaml
        try:
            return yaml.safe_dump(self.model_dump(exclude_none=True), default_flow_style=False, sort_keys=False)
        except Exception as e:
            print(f"Warning: safe_dump failed in to_yaml, using regular dump: {e}")
            return yaml.dump(self.model_dump(exclude_none=True), default_flow_style=False, sort_keys=False)
