"""Parse DSL commands and execute local operations in a disposable store."""

from demo_store import isolated_demo

from planfile import DSLExecutor, DSLParser


def run_checked(executor, command):
    """Surface a DSL failure instead of printing a misleading successful exit."""
    result = executor.run(command)
    if not result.ok:
        raise RuntimeError(f"{command}: {result.error}")
    print(result.message or result.data)
    return result


@isolated_demo
def example_basic_dsl():
    """Create, update and read an actual ticket in the demonstration store."""
    executor = DSLExecutor(project_path=".")
    run_checked(executor, "list tickets sprint=current")
    created = run_checked(executor, 'create ticket "Fix login bug" priority=high sprint=current')
    run_checked(executor, f"update ticket {created.data['id']} status=done")
    run_checked(executor, "query tickets where status=done priority=high")
    run_checked(executor, "export format=yaml")


@isolated_demo
def example_parser_only():
    """Parse a command without executing it."""
    parser = DSLParser()
    command = parser.parse('create ticket "New feature" priority=high labels=backend,auth')
    print(f"Verb: {command.verb}")
    print(f"Object: {command.object_type}")
    print(f"Target: {command.target}")
    print(f"Params: {command.params}")


@isolated_demo
def main():
    """Run local examples; remote sync and strategy validation need explicit setup."""
    print("DSL Examples")
    example_parser_only()
    example_basic_dsl()


if __name__ == "__main__":
    main()
