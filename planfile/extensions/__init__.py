"""Extensions for planfile - logger, analytics, and utilities."""

import traceback
from datetime import datetime
from typing import Any, Callable

from planfile import Planfile, Ticket, TicketSource


class TicketLogger:
    """
    Logger that creates tickets for errors, warnings, and alerts.
    
    Example:
        logger = TicketLogger("my-tool")
        
        # Log error as ticket
        logger.error("Database connection failed", context={"db": "prod"})
        
        # Log metric alert
        logger.metric_alert("CPU", 95, threshold=90)
        
        # Use as decorator
        @logger.catch_errors
        def risky_function():
            ...
    """
    
    def __init__(self, tool_name: str, auto_create: bool = True):
        self.tool_name = tool_name
        self.pf = Planfile.auto_discover()
        self.auto_create = auto_create
    
    def error(
        self,
        message: str,
        exception: Exception = None,
        context: dict = None,
        priority: str = "high"
    ) -> Ticket:
        """Create error ticket with optional exception details."""
        ctx = context or {}
        if exception:
            ctx["exception"] = str(exception)
            ctx["exception_type"] = type(exception).__name__
            ctx["traceback"] = traceback.format_exc()
        
        return self.pf.create_ticket(
            title=f"[{self.tool_name}] {message[:80]}",
            description=message,
            priority=priority,
            source=TicketSource(tool=self.tool_name, context=ctx),
            labels=["error", "auto-generated"]
        )
    
    def warning(self, message: str, context: dict = None) -> Ticket:
        """Create warning ticket."""
        return self.pf.create_ticket(
            title=f"[{self.tool_name}] {message[:80]}",
            description=message,
            priority="medium",
            source=TicketSource(tool=self.tool_name, context=context or {}),
            labels=["warning", "auto-generated"]
        )
    
    def metric_alert(
        self,
        metric: str,
        value: float,
        threshold: float,
        priority: str = "critical",
        **context
    ) -> Ticket:
        """Create ticket for metric threshold breach."""
        return self.pf.create_ticket(
            title=f"🚨 {metric}: {value} exceeds {threshold}",
            description=f"Metric {metric} exceeded threshold of {threshold}",
            priority=priority,
            source=TicketSource(
                tool=f"{self.tool_name}-metrics",
                context={
                    "metric": metric,
                    "value": value,
                    "threshold": threshold,
                    "timestamp": datetime.utcnow().isoformat(),
                    **context
                }
            ),
            labels=["alert", "metric", "auto-generated"]
        )
    
    def catch_errors(self, func: Callable) -> Callable:
        """Decorator to auto-log function errors as tickets."""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.error(
                    f"{func.__name__} failed: {str(e)[:60]}",
                    exception=e,
                    context={"function": func.__name__, "args": str(args), "kwargs": str(kwargs)}
                )
                raise
        return wrapper
