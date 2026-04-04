#!/usr/bin/env python3
"""
Simplified integration example using native TicketLogger.

BEFORE: 200 lines (manual implementation)
AFTER: 40 lines (using native API)
"""

from planfile.extensions import TicketLogger


def main():
    """Run simplified integration examples."""
    print("\n" + "="*60)
    print("Simplified Integration - Using TicketLogger")
    print("="*60 + "\n")
    
    # Initialize logger
    logger = TicketLogger("my-service")
    
    # 1. Log error with automatic context
    print("1. Error logging:")
    try:
        raise RuntimeError("Database connection failed")
    except Exception as e:
        ticket = logger.error("DB connection error", exception=e, context={"db": "prod"})
        print(f"   Created: {ticket.id}")
    
    # 2. Metric alert
    print("\n2. Metric alert:")
    ticket = logger.metric_alert("CPU", 95, threshold=90, server="prod-01")
    print(f"   Created: {ticket.id}")
    
    # 3. Decorator for automatic error tracking
    print("\n3. Error decorator:")
    
    @logger.catch_errors
    def risky_operation():
        raise ValueError("Something went wrong")
    
    try:
        risky_operation()
    except:
        print("   Error tracked as ticket")
    
    print("\n" + "="*60)
    print("Done! Check tickets with: pf.list_tickets()")
    print("="*60)


if __name__ == "__main__":
    main()
