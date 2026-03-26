from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class TaskType(str, Enum):
    """Type of task in the strategy."""
    feature = "feature"
    tech_debt = "tech_debt"
    bug = "bug"
    chore = "chore"
    documentation = "documentation"


class ModelTier(str, Enum):
    """Model tier for different phases of work."""
    local = "local"
    cheap = "cheap"
    balanced = "balanced"
    premium = "premium"


class ModelHints(BaseModel):
    """AI model hints for different phases of task execution."""
    design: Optional[ModelTier] = None
    implementation: Optional[ModelTier] = None
    review: Optional[ModelTier] = None
    triage: Optional[ModelTier] = None


class TaskPattern(BaseModel):
    """A pattern for generating tasks."""
    id: str = Field(..., description="Unique identifier for the pattern")
    type: TaskType = Field(..., description="Type of task")
    title: str = Field(..., description="Template for task title")
    description: str = Field(..., description="Template for task description")
    priority: Optional[str] = Field(None, description="Default priority")
    estimate: Optional[str] = Field(None, description="Default estimate (e.g., '3d', '1w')")
    labels: List[str] = Field(default_factory=list, description="Default labels")
    model_hints: ModelHints = Field(default_factory=ModelHints, description="AI model hints")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class Sprint(BaseModel):
    """A sprint in the strategy."""
    id: int = Field(..., description="Sprint number")
    name: str = Field(..., description="Sprint name")
    length_days: int = Field(14, description="Sprint length in days")
    objectives: List[str] = Field(default_factory=list, description="Sprint objectives")
    start_date: Optional[str] = Field(None, description="Start date (ISO format)")
    tasks: List[str] = Field(default_factory=list, description="Task pattern IDs for this sprint")


class QualityGate(BaseModel):
    """Quality gate definition."""
    name: str = Field(..., description="Gate name")
    description: str = Field(..., description="Gate description")
    criteria: List[str] = Field(..., description="Criteria to pass the gate")
    required: bool = Field(True, description="Whether this gate is required")


class Strategy(BaseModel):
    """Main strategy configuration."""
    name: str = Field(..., description="Strategy name")
    project_type: str = Field(..., description="Type of project (e.g., 'web', 'mobile', 'api')")
    domain: str = Field(..., description="Business domain")
    goal: str = Field(..., description="Main goal of this strategy")
    description: Optional[str] = Field(None, description="Detailed description")
    
    # Sprint configuration
    sprints: List[Sprint] = Field(default_factory=list, description="Sprints in this strategy")
    
    # Task patterns
    tasks: Dict[str, List[TaskPattern]] = Field(
        default_factory=lambda: {"patterns": []},
        description="Task patterns by category"
    )
    
    # Quality gates
    quality_gates: List[QualityGate] = Field(default_factory=list, description="Quality gates")
    
    # Strategy metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Metrics and KPIs
    success_metrics: List[str] = Field(default_factory=list, description="Success metrics")
    
    def get_task_patterns(self, category: str = "patterns") -> List[TaskPattern]:
        """Get task patterns by category."""
        return self.tasks.get(category, [])
    
    def get_sprint(self, sprint_id: int) -> Optional[Sprint]:
        """Get sprint by ID."""
        for sprint in self.sprints:
            if sprint.id == sprint_id:
                return sprint
        return None
