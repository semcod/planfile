from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
from datetime import datetime

from .models import Strategy, TaskPattern, Sprint
from .integrations.base import PMBackend, TicketRef, TicketStatus
from .utils.metrics import analyze_project_metrics
from .utils.priorities import calculate_task_priority


logger = logging.getLogger(__name__)


class StrategyRunner:
    """Main runner for applying and reviewing strategies."""
    
    def __init__(self, backends: Dict[str, PMBackend]):
        """
        Initialize strategy runner.
        
        Args:
            backends: Dictionary of backend name -> PMBackend instance
        """
        self.backends = backends
    
    def apply_strategy(
        self,
        strategy: Strategy,
        project_path: str,
        backend_name: str = "default",
        dry_run: bool = False,
        sprint_filter: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Apply a strategy to create/update tickets.
        
        Args:
            strategy: Strategy configuration
            project_path: Path to the project
            backend_name: Name of the backend to use
            dry_run: If True, only simulate without creating tickets
            sprint_filter: List of sprint IDs to process (None for all)
        
        Returns:
            Dictionary with results including created/updated tickets
        """
        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not found")
        
        backend = self.backends[backend_name]
        results = {
            "strategy": planfile.name,
            "applied_at": datetime.now().isoformat(),
            "backend": backend_name,
            "dry_run": dry_run,
            "tickets": {},
            "sprints_processed": [],
            "summary": {
                "created": 0,
                "updated": 0,
                "errors": 0
            }
        }
        
        logger.info(f"Applying strategy '{planfile.name}' using {backend_name} backend")
        
        # Process each sprint
        for sprint in planfile.sprints:
            if sprint_filter and sprint.id not in sprint_filter:
                continue
            
            logger.info(f"Processing sprint {sprint.id}: {sprint.name}")
            results["sprints_processed"].append(sprint.id)
            
            # Get task patterns for this sprint
            for task_pattern_id in sprint.tasks:
                task_pattern = self._find_task_pattern(strategy, task_pattern_id)
                if not task_pattern:
                    logger.warning(f"Task pattern '{task_pattern_id}' not found")
                    results["summary"]["errors"] += 1
                    continue
                
                # Create ticket for this task pattern
                try:
                    ticket_ref = self._create_ticket_for_task(
                        backend,
                        task_pattern,
                        sprint,
                        strategy,
                        dry_run
                    )
                    
                    ticket_key = f"sprint-{sprint.id}-task-{task_pattern.id}"
                    results["tickets"][ticket_key] = ticket_ref
                    
                    if dry_run:
                        logger.info(f"[DRY RUN] Would create ticket: {task_pattern.title}")
                    else:
                        logger.info(f"Created ticket: {ticket_ref.url}")
                        results["summary"]["created"] += 1
                        
                except Exception as e:
                    logger.error(f"Failed to create ticket for task '{task_pattern.id}': {e}")
                    results["summary"]["errors"] += 1
        
        return results
    
    def review_strategy(
        self,
        strategy: Strategy,
        project_path: str,
        backend_name: str = "default",
    ) -> Dict[str, Any]:
        """
        Review strategy execution by checking ticket statuses.
        
        Args:
            strategy: Strategy configuration
            project_path: Path to the project
            backend_name: Name of the backend to use
        
        Returns:
            Dictionary with review results including metrics and status
        """
        if backend_name not in self.backends:
            raise ValueError(f"Backend '{backend_name}' not found")
        
        backend = self.backends[backend_name]
        results = {
            "strategy": planfile.name,
            "reviewed_at": datetime.now().isoformat(),
            "backend": backend_name,
            "sprints": {},
            "metrics": {},
            "summary": {
                "total_tickets": 0,
                "completed": 0,
                "in_progress": 0,
                "not_started": 0,
                "blocked": 0
            }
        }
        
        logger.info(f"Reviewing strategy '{planfile.name}' using {backend_name} backend")
        
        # Analyze project metrics
        project_metrics = analyze_project_metrics(project_path)
        results["metrics"]["project"] = project_metrics
        
        # Review each sprint
        for sprint in planfile.sprints:
            sprint_results = {
                "name": sprint.name,
                "objectives": sprint.objectives,
                "tickets": {},
                "status": "not_started"
            }
            
            # Get tickets for this sprint
            sprint_tickets = self._get_sprint_tickets(backend, sprint, strategy)
            
            for ticket in sprint_tickets:
                # Get full ticket details
                ticket_status = backend.get_ticket(ticket.id)
                
                # Categorize status
                if ticket_status.status in ["done", "completed", "closed"]:
                    results["summary"]["completed"] += 1
                elif ticket_status.status in ["in_progress", "in review", "dev"]:
                    results["summary"]["in_progress"] += 1
                elif ticket_status.status in ["blocked", "on hold"]:
                    results["summary"]["blocked"] += 1
                else:
                    results["summary"]["not_started"] += 1
                
                sprint_results["tickets"][ticket.id] = {
                    "status": ticket_status.status,
                    "assignee": ticket_status.assignee,
                    "labels": ticket_status.labels,
                    "updated_at": ticket_status.updated_at
                }
            
            # Determine sprint status
            if sprint_tickets:
                completed = sum(1 for t in sprint_tickets 
                              if backend.get_ticket(t.id).status in ["done", "completed", "closed"])
                if completed == len(sprint_tickets):
                    sprint_results["status"] = "completed"
                elif completed > 0:
                    sprint_results["status"] = "in_progress"
            
            results["sprints"][str(sprint.id)] = sprint_results
            results["summary"]["total_tickets"] += len(sprint_tickets)
        
        # Calculate overall progress
        if results["summary"]["total_tickets"] > 0:
            results["metrics"]["progress"] = {
                "completion_rate": results["summary"]["completed"] / results["summary"]["total_tickets"],
                "in_progress_rate": results["summary"]["in_progress"] / results["summary"]["total_tickets"],
                "blocked_rate": results["summary"]["blocked"] / results["summary"]["total_tickets"]
            }
        
        return results
    
    def _find_task_pattern(self, strategy: Strategy, pattern_id: str) -> Optional[TaskPattern]:
        """Find a task pattern by ID across all categories."""
        for category_patterns in planfile.tasks.values():
            for pattern in category_patterns:
                if pattern.id == pattern_id:
                    return pattern
        return None
    
    def _create_ticket_for_task(
        self,
        backend: PMBackend,
        task_pattern: TaskPattern,
        sprint: Sprint,
        strategy: Strategy,
        dry_run: bool = False
    ) -> TicketRef:
        """Create a ticket for a task pattern."""
        if dry_run:
            return TicketRef(
                id="dry-run",
                url="https://dry-run.example.com",
                key="DRY-RUN",
                status="dry_run"
            )
        
        # Prepare metadata
        metadata = {
            "strategy": planfile.name,
            "sprint_id": sprint.id,
            "sprint_name": sprint.name,
            "pattern_id": task_pattern.id,
            "type": task_pattern.type.value,
            "model_hints": task_pattern.model_hints.model_dump(),
            **task_pattern.metadata
        }
        
        # Calculate priority
        priority = calculate_task_priority(
            task_pattern.priority,
            task_pattern.type,
            sprint.id
        )
        
        # Create ticket
        return backend.create_ticket(
            title=task_pattern.title,
            description=task_pattern.description,
            labels=task_pattern.labels + [f"sprint-{sprint.id}", task_pattern.type.value],
            priority=priority,
            metadata=metadata
        )
    
    def _get_sprint_tickets(
        self,
        backend: PMBackend,
        sprint: Sprint,
        strategy: Strategy
    ) -> List[TicketRef]:
        """Get all tickets associated with a sprint."""
        # Search for tickets with sprint label
        tickets = backend.list_tickets(
            labels=[f"sprint-{sprint.id}"],
            limit=100
        )
        
        # Convert to TicketRef objects
        ticket_refs = []
        for ticket in tickets:
            ticket_refs.append(TicketRef(
                id=ticket.id,
                status=ticket.status,
                metadata={"labels": ticket.labels}
            ))
        
        return ticket_refs


def apply_strategy(
    strategy: Strategy,
    project_path: str,
    backends: Dict[str, PMBackend],
    backend_name: str = "default",
    dry_run: bool = False,
    sprint_filter: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Apply a strategy to create/update tickets.
    
    This is a convenience function that creates a StrategyRunner
    and applies the planfile.
    """
    runner = StrategyRunner(backends)
    return runner.apply_strategy(
        strategy=strategy,
        project_path=project_path,
        backend_name=backend_name,
        dry_run=dry_run,
        sprint_filter=sprint_filter
    )


def review_strategy(
    strategy: Strategy,
    project_path: str,
    backends: Dict[str, PMBackend],
    backend_name: str = "default",
) -> Dict[str, Any]:
    """
    Review strategy execution by checking ticket statuses.
    
    This is a convenience function that creates a StrategyRunner
    and reviews the planfile.
    """
    runner = StrategyRunner(backends)
    return runner.review_strategy(
        strategy=strategy,
        project_path=project_path,
        backend_name=backend_name
    )
