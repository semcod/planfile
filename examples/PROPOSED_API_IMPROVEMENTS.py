"""
Proposed extended API for planfile package.

These features would allow reducing example code by ~60%.
"""

# ============================================================
# PROPOSED: planfile.extensions module
# ============================================================

class TicketLogger:
    """
    Native ticket logging - replaces 80-line example.
    
    Usage:
        from planfile import TicketLogger
        logger = TicketLogger("my-tool")
        
        @logger.catch_errors  # decorator
        def risky_function():
            ...
        
        logger.metric_alert("CPU", 95, threshold=90)
        logger.error("Database connection failed", context={"db": "prod"})
    """
    
    def __init__(self, tool_name: str, auto_create: bool = True):
        self.tool_name = tool_name
        self.pf = Planfile.auto_discover()
        self.auto_create = auto_create
    
    def error(self, message: str, exception=None, context: dict = None) -> "Ticket":
        """Create error ticket with optional exception details."""
        ctx = context or {}
        if exception:
            import traceback
            ctx["exception"] = str(exception)
            ctx["traceback"] = traceback.format_exc()
        
        return self.pf.create_ticket(
            title=f"[{self.tool_name}] {message[:80]}",
            priority="high",
            source=TicketSource(tool=self.tool_name, context=ctx),
            labels=["error", "auto-generated"]
        )
    
    def metric_alert(self, metric: str, value: float, threshold: float, **context) -> "Ticket":
        """Create ticket for threshold breach."""
        return self.pf.create_ticket(
            title=f"🚨 {metric}: {value} exceeds {threshold}",
            priority="critical",
            source=TicketSource(
                tool=f"{self.tool_name}-metrics",
                context={"metric": metric, "value": value, "threshold": threshold, **context}
            ),
            labels=["alert", "metric", "auto-generated"]
        )
    
    def catch_errors(self, func):
        """Decorator to auto-log function errors as tickets."""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.error(
                    f"{func.__name__} failed: {str(e)[:60]}",
                    exception=e,
                    context={"args": str(args), "kwargs": str(kwargs)}
                )
                raise
        return wrapper


# ============================================================
# PROPOSED: PlanfileStore extensions
# ============================================================

class PlanfileStoreExtended:
    """
    Extended store with analytics and export.
    """
    
    def stats(self) -> dict:
        """
        Get ticket statistics - replaces 30-line example.
        
        Returns:
            {
                "total": 100,
                "by_status": {"open": 30, "done": 50, ...},
                "by_priority": {"high": 20, "normal": 60, ...},
                "by_label": {"bug": 15, "feature": 25, ...},
                "by_sprint": {"current": 40, "backlog": 20, ...}
            }
        """
        tickets = self.list_tickets()
        from collections import Counter
        
        return {
            "total": len(tickets),
            "by_status": Counter(t.status.value if hasattr(t.status, 'value') else str(t.status) for t in tickets),
            "by_priority": Counter(t.priority for t in tickets),
            "by_label": Counter(label for t in tickets for label in (t.labels or [])),
            "by_sprint": Counter(t.sprint for t in tickets)
        }
    
    def export(self, format: str = "json", filter_sprint: str = None, **filters) -> str:
        """
        Export tickets to various formats - replaces 20-line example.
        
        Usage:
            csv_data = pf.store.export("csv", sprint="current")
            md_data = pf.store.export("markdown", status="open")
        """
        tickets = self.list_tickets(**filters)
        if filter_sprint:
            tickets = [t for t in tickets if t.sprint == filter_sprint]
        
        if format == "json":
            import json
            return json.dumps([t.model_dump() for t in tickets], indent=2)
        
        elif format == "csv":
            import csv
            import io
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["id", "title", "status", "priority", "sprint", "labels"])
            for t in tickets:
                writer.writerow([
                    t.id, t.title, 
                    t.status.value if hasattr(t.status, 'value') else t.status,
                    t.priority, t.sprint,
                    "|".join(t.labels or [])
                ])
            return output.getvalue()
        
        elif format == "markdown":
            lines = ["# Tickets\n"]
            for t in tickets:
                lines.append(f"- **{t.id}** [{t.priority}] {t.title}")
                lines.append(f"  - Status: {t.status}, Sprint: {t.sprint}")
                if t.labels:
                    lines.append(f"  - Labels: {', '.join(t.labels)}")
            return "\n".join(lines)
        
        else:
            raise ValueError(f"Unknown format: {format}")
    
    def search(self, query: str, search_fields: list = None) -> list:
        """
        Full-text search in tickets - not present in examples.
        
        Usage:
            results = pf.store.search("authentication", search_fields=["title", "description"])
        """
        search_fields = search_fields or ["title", "description"]
        tickets = self.list_tickets()
        query_lower = query.lower()
        
        results = []
        for t in tickets:
            for field in search_fields:
                value = getattr(t, field, "")
                if value and query_lower in str(value).lower():
                    results.append(t)
                    break
        return results


# ============================================================
# PROPOSED: Enhanced filters in list_tickets()
# ============================================================

# Current API:
#   pf.list_tickets(sprint="current", status="open")

# Proposed extended API:
#   pf.list_tickets(
#       sprint="current",
#       status="open", 
#       priority="high",
#       labels=["bug", "backend"],  # NEW: filter by labels (AND logic)
#       labels_any=True,           # NEW: OR logic instead of AND
#       created_after="2024-01-01", # NEW: date filtering
#       search="auth",             # NEW: full-text search
#   )


# ============================================================
# COMPARISON: Before vs After
# ============================================================

# BEFORE (current examples - verbose):
"""
# 04_advanced_filtering.py - ~60 lines
pf = Planfile.auto_discover()
all_tickets = pf.list_tickets()
status_counts = Counter(t.status for t in all_tickets)
priority_counts = Counter(t.priority for t in all_tickets)
all_labels = [label for t in all_tickets for label in (t.labels or [])]
label_counts = Counter(all_labels)
print(f"By Status: {dict(status_counts)}")
print(f"By Priority: {dict(priority_counts)}")
print(f"By Label: {dict(label_counts)}")
"""

# AFTER (with native API):
"""
# 04_analytics.py - ~10 lines  
pf = Planfile.auto_discover()
stats = pf.store.stats()
print(f"Total: {stats['total']}")
print(f"By Status: {stats['by_status']}")
print(f"By Priority: {stats['by_priority']}")
csv = pf.store.export("csv", sprint="current")
"""
