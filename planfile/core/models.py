"""
Planfile core models — merged from models.py + models_v2.py + new Ticket type.

This is the single canonical source for all planfile data models.
"""

from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

import yaml


class TaskType(str, Enum):
    """Type of task in the planfile."""
    feature = "feature"
    tech_debt = "tech_debt"
    bug = "bug"
    chore = "chore"
    documentation = "documentation"
    refactor = "refactor"
    test = "test"


class ModelTier(str, Enum):
    """Model tier for different phases of work."""
    local = "local"
    cheap = "cheap"
    balanced = "balanced"
    premium = "premium"
    free = "free"  # Alias for cheap


class ModelHints(BaseModel):
    """AI model hints for different phases of task execution."""
    design: Optional[ModelTier] = None
    implementation: Optional[ModelTier] = None
    review: Optional[ModelTier] = None
    triage: Optional[ModelTier] = None

    @field_validator('*', mode='before')
    @classmethod
    def convert_str_to_tier(cls, v):
        if isinstance(v, str) and v not in ModelTier.__members__:
            if v == "free":
                return ModelTier.cheap
        return v


class Task(BaseModel):
    """A task in a sprint - simplified and directly embedded."""
    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Task description")
    type: TaskType = Field(TaskType.feature, description="Type of task")
    priority: Optional[str] = Field("medium", description="Priority: low, medium, high")
    model_hints: Optional[Dict[str, str]] = Field(default_factory=dict, description="Model preferences")
    estimate: Optional[str] = Field(None, description="Estimate (e.g., '3d', '1w')")
    tags: List[str] = Field(default_factory=list, description="Tags for organization")

    @field_validator('model_hints', mode='before')
    @classmethod
    def normalize_model_hints(cls, v):
        if isinstance(v, str):
            return {"implementation": v}
        elif isinstance(v, dict):
            return v
        return {}


# Backward compatibility alias
TaskPattern = Task


class Sprint(BaseModel):
    """A sprint in the planfile."""
    id: Union[int, str] = Field(..., description="Sprint number or ID")
    name: str = Field(..., description="Sprint name")
    objectives: List[str] = Field(default_factory=list, description="Sprint objectives")
    tasks: List[Task] = Field(default_factory=list, description="Tasks in this sprint")
    length_days: Optional[int] = Field(14, description="Sprint length in days")
    duration: Optional[str] = Field(None, description="Sprint duration (e.g., '2 weeks')")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")

    @field_validator('tasks', mode='before')
    @classmethod
    def convert_tasks(cls, v):
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
    description: Optional[str] = Field(None, description="Gate description")
    criteria: Union[str, List[str]] = Field(..., description="Criteria to pass the gate")
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
    quality: List[str] = Field(default_factory=list, description="Quality goals")
    delivery: List[str] = Field(default_factory=list, description="Delivery goals")
    metrics: List[str] = Field(default_factory=list, description="Metric goals")


class Strategy(BaseModel):
    """Main strategy configuration - simplified and more flexible."""
    name: str = Field(..., description="Strategy name")
    version: Optional[str] = Field("1.0.0", description="Strategy version")
    project_type: Optional[str] = Field("software", description="Type of project")
    domain: Optional[str] = Field("software", description="Business domain")

    # Goal can be string or Goal object
    goal: Optional[str] = Field(None, description="Main goal of this strategy")
    description: Optional[str] = Field(None, description="Detailed description")

    # Sprints - the main structure
    sprints: List[Sprint] = Field(default_factory=list, description="Sprints in this strategy")

    # Task patterns (v1 compat)
    tasks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task patterns by category (v1 compat)"
    )

    # Quality gates
    quality_gates: List[QualityGate] = Field(default_factory=list, description="Quality gates")

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def get_task_patterns(self, category: str = None) -> List[Task]:
        """Get all tasks from all sprints (or patterns by category for v1 compat)."""
        if category and isinstance(self.tasks, dict):
            return self.tasks.get(category, [])
        all_tasks = []
        for sprint in self.sprints:
            all_tasks.extend(sprint.tasks)
        return all_tasks

    def get_sprint(self, sprint_id: int) -> Optional[Sprint]:
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

    @classmethod
    def model_validate_yaml(cls, yaml_content: str) -> "Strategy":
        """Load strategy from YAML string."""
        data = yaml.safe_load(yaml_content)

        # Convert task types
        if 'tasks' in data and isinstance(data['tasks'], dict) and 'patterns' in data['tasks']:
            for pattern in data['tasks']['patterns']:
                if 'type' in pattern and isinstance(pattern['type'], str):
                    try:
                        pattern['type'] = TaskType(pattern['type'])
                    except ValueError:
                        pass

        return cls.model_validate(data)

    def model_dump_yaml(self) -> str:
        """Dump model to YAML string."""
        data = self.model_dump()

        def convert_enums(obj):
            if isinstance(obj, dict):
                return {k: convert_enums(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_enums(item) for item in obj]
            elif hasattr(obj, 'value'):
                return obj.value
            else:
                return obj

        data = convert_enums(data)
        return yaml.dump(data, default_flow_style=False, sort_keys=False)

    def to_llx_format(self) -> Dict:
        """Convert to LLX-compatible format."""
        data = self.model_dump(mode='json')

        if isinstance(data.get('goal'), str):
            data['goal'] = {
                'short': data['goal'],
                'quality': [], 'delivery': [], 'metrics': []
            }
        elif isinstance(data.get('goal'), dict):
            goal = data['goal']
            if 'short' not in goal:
                goal['short'] = str(goal)
            goal.setdefault('quality', [])
            goal.setdefault('delivery', [])
            goal.setdefault('metrics', [])

        for sprint in data.get('sprints', []):
            if 'tasks' in sprint:
                task_patterns = []
                for task in sprint['tasks']:
                    if isinstance(task, dict):
                        pattern = {
                            'name': task.get('name', 'unnamed'),
                            'description': task.get('description', ''),
                            'task_type': task.get('type', 'feature'),
                            'model_hint': task.get('model_hints', {}).get('implementation', 'balanced')
                        }
                        task_patterns.append(pattern)
                    else:
                        task_patterns.append(task)
                sprint['task_patterns'] = task_patterns
                sprint['tasks'] = [f"task-{i+1}" for i in range(len(task_patterns))]

        return data

    def compare(self, other: 'Strategy') -> Dict[str, Any]:
        """Compare with another strategy and return differences."""
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

    def merge(self, others: List['Strategy'], name: str = None) -> 'Strategy':
        """Merge with other strategies to create a combined strategy."""
        if not others:
            return self

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
        sprint_id = 1
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
        if format.lower() == 'yaml':
            return yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)
        elif format.lower() == 'json':
            import json
            return json.dumps(self.model_dump(), indent=2, default=str)
        elif format.lower() == 'dict':
            return self.model_dump()
        else:
            raise ValueError(f"Unsupported export format: {format}")

    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics."""
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
                        durations.append(weeks * 7)
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

    @classmethod
    def load_flexible(cls, data: Union[Dict, str, Path]) -> "Strategy":
        """Load strategy from various formats with error tolerance."""
        if isinstance(data, (str, Path)):
            data = yaml.safe_load(Path(data).read_text(encoding="utf-8"))

        if isinstance(data, dict):
            if 'tasks' in data and isinstance(data['tasks'], dict) and 'patterns' in data['tasks']:
                data = cls._convert_old_format(data)

            if 'goal' in data and isinstance(data['goal'], dict):
                data['goal'] = Goal(**data['goal'])

            data.setdefault('version', '1.0.0')
            data.setdefault('project_type', 'software')
            data.setdefault('domain', 'software')

            return cls(**data)

        raise ValueError("Invalid strategy data")

    @staticmethod
    def _convert_old_format(data: Dict) -> Dict:
        """Convert old format with separate task patterns to new format."""
        task_patterns = {tp['id']: tp for tp in data.get('tasks', {}).get('patterns', [])}

        for sprint in data.get('sprints', []):
            tasks = []
            for task_id in sprint.get('tasks', []):
                if isinstance(task_id, str) and task_id in task_patterns:
                    tasks.append(Task(**task_patterns[task_id]))
            if tasks:
                sprint['tasks'] = tasks

        return data

    def to_yaml(self) -> str:
        """Export to YAML with clean formatting."""
        return yaml.dump(self.model_dump(exclude_none=True), default_flow_style=False, sort_keys=False)


# ─── Ticket types (new in Sprint 3) ───

class TicketStatus(str, Enum):
    """Status of a ticket."""
    open = "open"
    in_progress = "in_progress"
    review = "review"
    done = "done"
    blocked = "blocked"


class TicketSource(BaseModel):
    """Who/what created the ticket."""
    tool: str                          # "code2llm" | "vallm" | "llx" | "human"
    version: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    context: dict = Field(default_factory=dict)


class Ticket(BaseModel):
    """Atomic unit of work in planfile."""
    id: str                            # "PLF-042"
    title: str
    status: TicketStatus = TicketStatus.open
    priority: str = "normal"           # critical | high | normal | low
    sprint: str = "current"            # current | backlog | sprint-XXX

    source: Optional[TicketSource] = None
    description: str = ""
    acceptance_criteria: List[str] = Field(default_factory=list)
    labels: List[str] = Field(default_factory=list)

    blocked_by: List[str] = Field(default_factory=list)
    blocks: List[str] = Field(default_factory=list)

    llm_hints: Optional[ModelHints] = None

    sync: dict = Field(default_factory=dict)  # {"github": {"issue": 142}}
    history: List[dict] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
