#!/usr/bin/env python3
"""
Integrating planfile into existing tools and workflows.

Shows how to:
- Add ticket creation to your CLI tools
- Log errors as tickets automatically
- Track metrics and alerts as tickets
"""

import sys
import traceback
from datetime import datetime
from planfile import quick_ticket, Planfile


class TicketLogger:
    """Logger that creates tickets for errors and warnings."""
    
    def __init__(self, tool_name):
        self.tool_name = tool_name
        self.pf = Planfile.auto_discover(".")
    
    def error(self, message, exception=None, context=None):
        """Log error as ticket."""
        ctx = context or {}
        if exception:
            ctx["exception"] = str(exception)
            ctx["traceback"] = traceback.format_exc()
        
        ticket = quick_ticket(
            title=f"[{self.tool_name}] Error: {message[:50]}",
            tool=self.tool_name,
            priority="high",
            description=message,
            context=ctx,
            type="bug"
        )
        print(f"🎫 Created error ticket: {ticket.id}")
        return ticket
    
    def warning(self, message, context=None):
        """Log warning as ticket."""
        ticket = quick_ticket(
            title=f"[{self.tool_name}] Warning: {message[:50]}",
            tool=self.tool_name,
            priority="medium",
            description=message,
            context=context or {},
            type="task"
        )
        print(f"🎫 Created warning ticket: {ticket.id}")
        return ticket
    
    def metric_alert(self, metric_name, value, threshold):
        """Create ticket for metric threshold breach."""
        ticket = quick_ticket(
            title=f"🚨 {metric_name}: {value} exceeds {threshold}",
            tool=f"{self.tool_name}-metrics",
            priority="critical",
            description=f"Metric {metric_name} exceeded threshold",
            context={
                "metric": metric_name,
                "value": value,
                "threshold": threshold,
                "timestamp": datetime.now().isoformat()
            },
            type="bug"
        )
        print(f"🎫 Created metric alert ticket: {ticket.id}")
        return ticket


def example_cli_tool_integration():
    """Show integration with a CLI tool."""
    print("=== Example: CLI Tool Integration ===\n")
    
    # Simulate a deployment tool that logs failures
    logger = TicketLogger("deploy-tool")
    
    try:
        # Simulate deployment failure
        raise RuntimeError("Failed to connect to production database")
    except Exception as e:
        logger.error(
            message="Deployment failed: Database connection error",
            exception=e,
            context={
                "environment": "production",
                "version": "2.1.0",
                "server": "prod-01"
            }
        )
    
    print()


def example_monitoring_integration():
    """Monitoring system integration."""
    print("=== Example: Monitoring Integration ===\n")
    
    logger = TicketLogger("system-monitor")
    
    # Simulate metric checks
    cpu_usage = 95  # Percentage
    memory_usage = 88
    disk_usage = 92
    
    if cpu_usage > 90:
        logger.metric_alert("CPU Usage", cpu_usage, 90)
    
    if memory_usage > 85:
        logger.metric_alert("Memory Usage", memory_usage, 85)
    
    if disk_usage > 90:
        logger.metric_alert("Disk Usage", disk_usage, 90)
    
    print()


def example_ci_pipeline_integration():
    """CI pipeline failure tracking."""
    print("=== Example: CI Pipeline Integration ===\n")
    
    logger = TicketLogger("ci-pipeline")
    
    # Simulate test failures
    test_results = {
        "tests/test_api.py::test_login": "FAILED",
        "tests/test_api.py::test_logout": "PASSED",
        "tests/test_db.py::test_connection": "FAILED"
    }
    
    failed_tests = [t for t, r in test_results.items() if r == "FAILED"]
    
    if failed_tests:
        logger.error(
            message=f"CI Pipeline failed: {len(failed_tests)} tests failed",
            context={
                "failed_tests": failed_tests,
                "total_tests": len(test_results),
                "branch": "main",
                "commit": "abc123"
            }
        )
    
    print()


def example_custom_decorator():
    """Decorator for automatic error tracking."""
    print("=== Example: Error Tracking Decorator ===\n")
    
    def track_errors(tool_name):
        """Decorator to track function errors as tickets."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    quick_ticket(
                        title=f"[{tool_name}] {func.__name__} failed: {str(e)[:40]}",
                        tool=tool_name,
                        priority="high",
                        description=f"Function {func.__name__} raised {type(e).__name__}",
                        context={
                            "function": func.__name__,
                            "exception": str(e),
                            "args": str(args),
                            "kwargs": str(kwargs)
                        },
                        type="bug"
                    )
                    raise  # Re-raise after logging
            return wrapper
        return decorator
    
    @track_errors("data-processor")
    def process_data(data):
        """Simulate data processing that might fail."""
        if not data:
            raise ValueError("Empty data provided")
        return sum(data) / len(data)
    
    # This will work
    try:
        result = process_data([1, 2, 3, 4, 5])
        print(f"✓ Processed successfully: {result}")
    except Exception:
        pass
    
    # This will fail and create a ticket
    try:
        process_data([])
    except Exception:
        print("✗ Error tracked as ticket")
    
    print()


def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Planfile Python Library - Tool Integration")
    print("="*60 + "\n")
    
    example_cli_tool_integration()
    example_monitoring_integration()
    example_ci_pipeline_integration()
    example_custom_decorator()
    
    print("="*60)
    print("Integration examples completed!")
    print("="*60)


if __name__ == "__main__":
    main()
