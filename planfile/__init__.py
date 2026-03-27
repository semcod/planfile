"""planfile — universal ticket standard for developer toolchains.

This package provides:
- Strategy and sprint modeling in YAML
- Ticket-based project management (CRUD, import, sync)
- Task execution with intelligent model selection
- Integration with various LLM providers
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.39"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

from pathlib import Path

# Core models (single source of truth)
from .core.models import (
    Strategy, Sprint, Task, TaskPattern, TaskType,
    ModelHints, ModelTier, Goal, QualityGate,
    Ticket, TicketStatus, TicketSource,
)
from .core.store import PlanfileStore

# Backward compat aliases
StrategyV1 = Strategy
StrategyV2 = Strategy
ModelTierV2 = ModelTier

# Executors
from . import runner
from . import executor_standalone
from .runner import load_valid_strategy, run_strategy, verify_strategy_post_execution
from .executor_standalone import StrategyExecutor, execute_strategy, TaskResult, LLMClient
from .executor_standalone import create_openai_client, create_litellm_client


class Planfile:
    """Main entry point — convenience wrapper around PlanfileStore."""

    def __init__(self, project_path: str = "."):
        self.store = PlanfileStore(project_path)
        if not self.store.is_initialized():
            self.store.init()

    @classmethod
    def auto_discover(cls, start_path: str = ".") -> "Planfile":
        """Find .planfile/ in CWD or parent directories."""
        path = Path(start_path).resolve()
        while path != path.parent:
            if (path / ".planfile").exists():
                return cls(str(path))
            path = path.parent
        return cls(start_path)  # init in CWD

    def create_ticket(self, title: str, **kwargs) -> Ticket:
        ticket_id = self.store.next_id()
        ticket = Ticket(id=ticket_id, title=title, **kwargs)
        return self.store.create_ticket(ticket)

    def get_ticket(self, ticket_id: str):
        return self.store.get_ticket(ticket_id)

    def list_tickets(self, **filters):
        return self.store.list_tickets(**filters)

    def update_ticket(self, ticket_id: str, **updates):
        return self.store.update_ticket(ticket_id, **updates)

    def create_tickets_bulk(self, tickets_data: list[dict],
                            source: str = None, sprint: str = "current"):
        created = []
        for data in tickets_data:
            if source and "source" not in data:
                data["source"] = {"tool": source}
            data.setdefault("sprint", sprint)
            ticket = self.create_ticket(**data)
            created.append(ticket)
        return created


def quick_ticket(title: str, tool: str = "unknown", **kwargs) -> Ticket:
    """One-liner ticket creation for tools."""
    pf = Planfile.auto_discover()
    source = TicketSource(tool=tool, context=kwargs.pop("context", {}))
    return pf.create_ticket(title=title, source=source, **kwargs)


__all__ = [
    # Models
    "Strategy", "StrategyV1", "StrategyV2",
    "Sprint", "Task", "TaskPattern", "TaskType",
    "ModelHints", "ModelTier", "ModelTierV2",
    "Goal", "QualityGate",
    # Tickets
    "Ticket", "TicketStatus", "TicketSource",
    # Store & API
    "PlanfileStore", "Planfile", "quick_ticket",
    # Executors
    "StrategyExecutor", "execute_strategy", "TaskResult", "LLMClient",
    "create_openai_client", "create_litellm_client",
    # Runner
    "load_valid_strategy", "run_strategy", "verify_strategy_post_execution",
]
