"""planfile — universal ticket standard for developer toolchains.

This package provides:
- Strategy and sprint modeling in YAML
- Ticket-based project management (CRUD, import, sync)
- Task execution with intelligent model selection
- Integration with various LLM providers
- CLI and API for applying and reviewing strategies
"""

__version__ = "0.1.93"
__author__ = "Tom Sapletta"
__email__ = "tom@sapletta.com"

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

# Core models (single source of truth)
from planfile.core.models import (
    Goal,
    ModelHints,
    ModelTier,
    QualityGate,
    Sprint,
    Strategy,
    Task,
    TaskPattern,
    TaskType,
    Ticket,
    TicketExecution,
    TicketExecutor,
    TicketInputs,
    TicketOutputs,
    TicketSource,
    TicketStatus,
)
from planfile.core.store import PlanfileStore
from planfile.dsl import DSLExecutor, DSLParser, DSLResult
from planfile.testql_integration import (
    build_testql_tickets,
    run_testql_validation,
    sync_testql_tickets,
    upsert_testql_tickets,
)
from planfile.ticket_validation import validate_planfile_tickets
from planfile.todo_sync import sync_todo_checkboxes_from_planfile

# Backward compat aliases
StrategyV1 = Strategy
StrategyV2 = Strategy
ModelTierV2 = ModelTier

# Lazy loading for executors to improve startup performance
if TYPE_CHECKING:
    from planfile import executor_standalone, runner
    from planfile.executor_standalone import (
        LLMClient,
        StrategyExecutor,
        TaskResult,
        create_litellm_client,
        create_openai_client,
        execute_strategy,
    )
    from planfile.runner import load_valid_strategy, run_strategy, verify_strategy_post_execution


class Planfile:
    """Main entry point — convenience wrapper around PlanfileStore."""

    MAX_BULK_TICKETS = 50

    @staticmethod
    def _utcnow() -> datetime:
        return datetime.now(UTC)

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

    def create_ticket(self, name: str, **kwargs) -> Ticket:
        ticket_id = self.store.next_id()
        ticket = Ticket(id=ticket_id, name=name, **kwargs)
        return self.store.create_ticket(ticket)

    def get_ticket(self, ticket_id: str):
        return self.store.get_ticket(ticket_id)

    def list_tickets(self, **filters):
        return self.store.list_tickets(**filters)

    def next_ticket(self, sprint: str = "current", queue: str | None = None) -> Ticket | None:
        """Return the next runnable ticket for queue-like workflows.
        
        Uses bug-first priority: bugs are always preferred over features
        when they have the same priority level.
        """
        priority_order = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        runnable_states = {"pending", "ready", ""}
        blocked_statuses = {"done", "canceled"}

        tickets = self.list_tickets(sprint=sprint, status="open")
        runnable: list[Ticket] = []

        for ticket in tickets:
            execution_state = (ticket.execution.state if ticket.execution else "") or ""
            if execution_state not in runnable_states:
                continue
            if queue and ((ticket.execution.queue if ticket.execution else "default") != queue):
                continue

            is_blocked = False
            for blocked_id in ticket.blocked_by:
                blocked_ticket = self.get_ticket(blocked_id)
                if not blocked_ticket:
                    is_blocked = True
                    break
                blocked_status = (
                    blocked_ticket.status.value
                    if hasattr(blocked_ticket.status, "value")
                    else str(blocked_ticket.status)
                )
                if blocked_status not in blocked_statuses:
                    is_blocked = True
                    break

            if not is_blocked:
                runnable.append(ticket)

        if not runnable:
            return None

        def _ticket_sort_key(ticket: Ticket):
            """Bug-first sorting key: priority, bug flag, created_at, id."""
            priority_score = priority_order.get(str(ticket.priority), 99)
            
            # Bug flag: bugs get 0, features get 1 (so bugs sort first)
            is_bug = 0 if ticket.labels and "bug" in ticket.labels else 1
            
            return (
                priority_score,
                is_bug,
                str(ticket.created_at),
                ticket.id,
            )

        return sorted(runnable, key=_ticket_sort_key)[0]

    def update_ticket(self, ticket_id: str, **updates):
        return self.store.update_ticket(ticket_id, **updates)

    @staticmethod
    def _merge_model(current, model_cls, **changes):
        data = current.model_dump(mode="python", exclude_none=True) if current else {}
        for key, value in changes.items():
            if value is not None:
                data[key] = value
        return model_cls(**data)

    def claim_ticket(
        self,
        ticket_id: str,
        assigned_to: str | None = None,
        lease_seconds: int | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        lease_expires_at = None
        if lease_seconds:
            lease_expires_at = self._utcnow() + timedelta(seconds=lease_seconds)

        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            assigned_to=assigned_to or (ticket.execution.assigned_to if ticket.execution else None),
            lease_expires_at=lease_expires_at,
            state="ready" if (ticket.execution.state if ticket.execution else "pending") == "pending" else None,
        )
        return self.update_ticket(ticket_id, execution=execution)

    def start_ticket(self, ticket_id: str, assigned_to: str | None = None) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="running",
            assigned_to=assigned_to or (ticket.execution.assigned_to if ticket.execution else None),
            started_at=ticket.execution.started_at if ticket.execution and ticket.execution.started_at else self._utcnow(),
        )
        return self.update_ticket(ticket_id, status="in_progress", execution=execution)

    def complete_ticket(
        self,
        ticket_id: str,
        note: str | None = None,
        result=None,
        artifacts: list[str] | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        existing_notes = list(ticket.outputs.notes) if ticket.outputs else []
        existing_artifacts = list(ticket.outputs.artifacts) if ticket.outputs else []
        outputs = self._merge_model(
            ticket.outputs,
            TicketOutputs,
            notes=existing_notes + ([note] if note else []),
            artifacts=existing_artifacts + list(artifacts or []),
            result=result if result is not None else (ticket.outputs.result if ticket.outputs else None),
        )
        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="done",
            finished_at=self._utcnow(),
            lease_expires_at=None,
            last_error=None,
        )
        return self.update_ticket(ticket_id, status="done", execution=execution, outputs=outputs)

    def fail_ticket(self, ticket_id: str, error: str) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        current_attempt = ticket.execution.attempt if ticket.execution else 0
        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="failed",
            finished_at=self._utcnow(),
            lease_expires_at=None,
            attempt=current_attempt + 1,
            last_error=error,
        )
        return self.update_ticket(ticket_id, execution=execution)

    def _append_note(self, ticket: Ticket, note: str) -> TicketOutputs:
        """Build an updated TicketOutputs with `note` appended to existing notes.

        Preserves existing artifacts and result. Shared by ready_ticket,
        wait_for_input and update_ticket --note (PLF-koru improvement #7).
        """
        existing_notes = list(ticket.outputs.notes) if ticket.outputs else []
        existing_artifacts = list(ticket.outputs.artifacts) if ticket.outputs else []
        return self._merge_model(
            ticket.outputs,
            TicketOutputs,
            notes=existing_notes + [note],
            artifacts=existing_artifacts,
            result=ticket.outputs.result if ticket.outputs else None,
        )

    def wait_for_input(
        self,
        ticket_id: str,
        prompt: str,
        env_keys: list[str] | None = None,
        note: str | None = None,
    ) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        existing_keys = list(ticket.inputs.env_keys) if ticket.inputs else []
        merged_keys = existing_keys + [key for key in (env_keys or []) if key not in existing_keys]
        inputs = self._merge_model(
            ticket.inputs,
            TicketInputs,
            prompt=prompt,
            env_keys=merged_keys,
        )
        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="waiting_input",
            lease_expires_at=None,
        )
        updates: dict = {"execution": execution, "inputs": inputs}
        if note:
            updates["outputs"] = self._append_note(ticket, note)
        return self.update_ticket(ticket_id, **updates)

    def ready_ticket(self, ticket_id: str, note: str | None = None) -> Ticket | None:
        ticket = self.get_ticket(ticket_id)
        if not ticket:
            return None

        execution = self._merge_model(
            ticket.execution,
            TicketExecution,
            state="ready",
            last_error=None,
        )
        updates: dict = {"execution": execution}
        if note:
            updates["outputs"] = self._append_note(ticket, note)
        return self.update_ticket(ticket_id, **updates)

    def delete_ticket(self, ticket_id: str) -> bool:
        """Delete a single ticket by ID. Returns True if deleted, False if not found."""
        return self.store.delete_ticket(ticket_id)

    def delete_tickets(self, ticket_ids: list[str]) -> tuple[list[str], list[str]]:
        """Delete multiple tickets by ID. Returns (deleted_ids, not_found_ids)."""
        return self.store.delete_tickets_bulk(ticket_ids)

    def create_tickets_bulk(self, tickets_data: list[dict],
                            source: str = None, sprint: str = "current"):
        created = []
        for data in tickets_data[:self.MAX_BULK_TICKETS]:
            if source and "source" not in data:
                data["source"] = {"tool": source}
            data.setdefault("sprint", sprint)
            ticket = self.create_ticket(**data)
            created.append(ticket)
        if len(tickets_data) > self.MAX_BULK_TICKETS:
            # Keep the limit explicit so callers can surface it in UX/logs.
            pass
        return created


def quick_ticket(name: str, tool: str = "unknown", **kwargs) -> Ticket:
    """One-liner ticket creation for tools."""
    pf = Planfile.auto_discover()
    source = TicketSource(tool=tool, context=kwargs.pop("context", {}))
    return pf.create_ticket(name=name, source=source, **kwargs)


__all__ = [
    # Models
    "Strategy", "StrategyV1", "StrategyV2",
    "Sprint", "Task", "TaskPattern", "TaskType",
    "ModelHints", "ModelTier", "ModelTierV2",
    "Goal", "QualityGate",
    # Tickets
    "Ticket", "TicketStatus", "TicketSource",
    "TicketExecutor", "TicketExecution", "TicketInputs", "TicketOutputs",
    # Store & API
    "PlanfileStore", "Planfile", "quick_ticket",
    # Executors (lazy loaded)
    "StrategyExecutor", "execute_strategy", "TaskResult", "LLMClient",
    "create_openai_client", "create_litellm_client",
    # Runner (lazy loaded)
    "load_valid_strategy", "run_strategy", "verify_strategy_post_execution",
    "sync_todo_checkboxes_from_planfile",
    "run_testql_validation",
    "build_testql_tickets",
    "upsert_testql_tickets",
    "sync_testql_tickets",
    "validate_planfile_tickets",
    # DSL
    "DSLParser", "DSLExecutor", "DSLResult",
]

# Lazy loading functions for executors
def __getattr__(name):
    """Lazy import executor modules when accessed."""
    if name in ["runner", "executor_standalone"]:
        import importlib
        return importlib.import_module(f"planfile.{name}")
    elif name in ["load_valid_strategy", "run_strategy", "verify_strategy_post_execution"]:
        from planfile.runner import (
            load_valid_strategy,
            run_strategy,
            verify_strategy_post_execution,
        )
        if name == "load_valid_strategy":
            return load_valid_strategy
        elif name == "run_strategy":
            return run_strategy
        else:
            return verify_strategy_post_execution
    elif name in ["StrategyExecutor", "execute_strategy", "TaskResult", "LLMClient",
                 "create_openai_client", "create_litellm_client"]:
        from planfile.executor_standalone import (
            LLMClient,
            StrategyExecutor,
            TaskResult,
            create_litellm_client,
            create_openai_client,
            execute_strategy,
        )
        if name == "StrategyExecutor":
            return StrategyExecutor
        elif name == "execute_strategy":
            return execute_strategy
        elif name == "TaskResult":
            return TaskResult
        elif name == "LLMClient":
            return LLMClient
        elif name == "create_openai_client":
            return create_openai_client
        else:
            return create_litellm_client
    raise AttributeError(f"module 'planfile' has no attribute '{name}'")
