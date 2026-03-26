"""Simplified, more robust planfile models based on testing experience."""

from enum import Enum
from typing import List, Dict, Optional, Any, Union
from pathlib import Path
from pydantic import BaseModel, Field, validator


class TaskType(str, Enum):
    """Type of task in the planfile."""
    feature = "feature"
    tech_debt = "tech_debt"
    bug = "bug"
    chore = "chore"
    documentation = "documentation"
    refactor = "refactor"  # Added for convenience
    test = "test"  # Added for convenience


class ModelTier(str, Enum):
    """Model tier for different phases of work."""
    local = "local"
    cheap = "cheap"  # Free models
    balanced = "balanced"
    premium = "premium"
    free = "free"  # Alias for cheap


class ModelHints(BaseModel):
    """AI model hints for different phases of task execution."""
    design: Optional[ModelTier] = None
    implementation: Optional[ModelTier] = None
    review: Optional[ModelTier] = None
    triage: Optional[ModelTier] = None
    
    # Allow string value for simplicity
    @validator('*', pre=True)
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
    
    # Allow flexible model hints
    @validator('model_hints', pre=True)
    def normalize_model_hints(cls, v):
        if isinstance(v, str):
            return {"implementation": v}
        elif isinstance(v, dict):
            return v
        return {}


class Sprint(BaseModel):
    """A sprint in the planfile - simplified."""
    id: int = Field(..., description="Sprint number")
    name: str = Field(..., description="Sprint name")
    objectives: List[str] = Field(default_factory=list, description="Sprint objectives")
    tasks: List[Task] = Field(default_factory=list, description="Tasks in this sprint")
    length_days: Optional[int] = Field(14, description="Sprint length in days")
    
    # Allow both task objects and simple dicts
    @validator('tasks', pre=True)
    def convert_tasks(cls, v):
        if isinstance(v, list):
            tasks = []
            for item in v:
                if isinstance(item, dict):
                    # Handle different task formats
                    if 'task_patterns' in item:
                        # Skip task_patterns, handled elsewhere
                        continue
                    elif 'name' in item:
                        tasks.append(Task(**item))
                    else:
                        # Simple format, create task from dict
                        tasks.append(Task(
                            name=item.get('title', 'Unnamed Task'),
                            description=item.get('description', ''),
                            type=item.get('type', TaskType.feature),
                            priority=item.get('priority', 'medium'),
                            model_hints=item.get('model_hints', {})
                        ))
            return tasks
        return v


class QualityGate(BaseModel):
    """Quality gate definition."""
    name: str = Field(..., description="Gate name")
    description: Optional[str] = Field(None, description="Gate description")
    criteria: Union[str, List[str]] = Field(..., description="Criteria to pass the gate")
    required: bool = Field(True, description="Whether this gate is required")
    
    # Allow string criteria
    @validator('criteria', pre=True)
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
    goal: Union[str, Goal] = Field(..., description="Main goal of this strategy")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Sprints - the main structure
    sprints: List[Sprint] = Field(default_factory=list, description="Sprints in this strategy")
    
    # Quality gates
    quality_gates: List[QualityGate] = Field(default_factory=list, description="Quality gates")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Helper methods
    def get_task_patterns(self) -> List[Task]:
        """Get all tasks from all sprints."""
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
    
    # Allow loading from various formats
    @classmethod
    def load_flexible(cls, data: Union[Dict, str, Path]) -> "Strategy":
        """Load strategy from various formats with error tolerance."""
        import yaml
        from pathlib import Path
        
        if isinstance(data, (str, Path)):
            data = yaml.safe_load(Path(data).read_text(encoding="utf-8"))
        
        # Handle different strategy formats
        if isinstance(data, dict):
            # Convert old format if needed
            if 'tasks' in data and 'patterns' in data['tasks']:
                # Old format with separate task patterns
                data = cls._convert_old_format(data)
            
            # Handle goal as string
            if 'goal' in data and isinstance(data['goal'], dict):
                data['goal'] = Goal(**data['goal'])
            
            # Handle missing required fields with defaults
            data.setdefault('version', '1.0.0')
            data.setdefault('project_type', 'software')
            data.setdefault('domain', 'software')
            
            return cls(**data)
        
        raise ValueError("Invalid strategy data")
    
    @staticmethod
    def _convert_old_format(data: Dict) -> Dict:
        """Convert old format with separate task patterns to new format."""
        # Create a map of task patterns
        task_patterns = {tp['id']: tp for tp in data.get('tasks', {}).get('patterns', [])}
        
        # Convert sprints to include tasks directly
        for sprint in data.get('sprints', []):
            tasks = []
            for task_id in sprint.get('tasks', []):
                if task_id in task_patterns:
                    tasks.append(Task(**task_patterns[task_id]))
            sprint['tasks'] = tasks
            # Remove old task_patterns and tasks list
            sprint.pop('task_patterns', None)
            sprint.pop('tasks', None)
        
        return data
    
    def to_yaml(self) -> str:
        """Export to YAML with clean formatting."""
        import yaml
        return yaml.dump(self.dict(exclude_none=True), default_flow_style=False, sort_keys=False)
