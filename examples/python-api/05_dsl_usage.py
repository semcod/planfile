"""DSL (Domain Specific Language) examples for planfile.

DSL allows natural language-like commands to operate on planfile YAML.
"""

from planfile import DSLExecutor, DSLParser


def example_basic_dsl():
    """Basic DSL command execution."""
    executor = DSLExecutor(project_path=".")

    # List all tickets in current sprint
    result = executor.run("list tickets sprint=current")
    print(result.ok, result.data, result.message)

    # Create a new ticket
    result = executor.run('create ticket "Fix login bug" priority=high sprint=1')
    print(result.ok, result.data)

    # Update ticket status
    result = executor.run("update ticket PLF-001 status=done")
    print(result.ok, result.message)


def example_parser_only():
    """Parse DSL commands without executing."""
    parser = DSLParser()

    cmd = parser.parse('create ticket "New feature" priority=high labels=backend,auth')
    print(f"Verb: {cmd.verb}")
    print(f"Object: {cmd.object_type}")
    print(f"Target: {cmd.target}")
    print(f"Params: {cmd.params}")

    cmd = parser.parse("list tickets sprint=current status=open")
    print(f"Filters: {cmd.params}")


def example_batch_operations():
    """Batch ticket operations using DSL."""
    executor = DSLExecutor(project_path=".")

    # Mark multiple tickets as done
    for ticket_id in ["PLF-001", "PLF-002", "PLF-003"]:
        result = executor.run(f"done ticket {ticket_id}")
        print(f"{ticket_id}: {result.ok}")

    # Move all high-priority tickets to sprint 2
    result = executor.run("query tickets where priority=high")
    if result.ok:
        for ticket in result.data:
            result = executor.run(f"move ticket {ticket['id']} to=2")


def example_sprint_management():
    """Sprint operations via DSL."""
    executor = DSLExecutor(project_path=".")

    # List sprints
    result = executor.run("list sprints")
    print(result.data)

    # Add new sprint
    result = executor.run('add sprint "Sprint 4" days=14')
    print(result.message)


def example_validation_sync():
    """Validation and sync via DSL."""
    executor = DSLExecutor(project_path=".")

    # Validate tickets
    result = executor.run("validate")
    print(result.message)

    # Sync to GitHub
    result = executor.run("sync github")
    print(result.message)

    # Sync all integrations
    result = executor.run("sync all")
    print(result.message)


def example_query_and_export():
    """Query tickets and export data."""
    executor = DSLExecutor(project_path=".")

    # Query with filters
    result = executor.run("query tickets where status=open priority=high")
    print(result.data)

    # Export to YAML
    result = executor.run("export format=yaml")
    print(result.data)


if __name__ == "__main__":
    print("DSL Examples")
    print("=" * 40)

    # Uncomment to run examples
    # example_basic_dsl()
    # example_parser_only()
    # example_batch_operations()
    # example_sprint_management()
    # example_validation_sync()
    # example_query_and_export()
