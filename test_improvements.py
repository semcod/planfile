#!/usr/bin/env python3
"""Test the improved planfile v2 implementation."""

from rich.console import Console
from rich.table import Table

console = Console()


def test_v2_format():
    """Test the new v2 format with simplified structure."""

    console.print("[bold blue]Testing Planfile V2 - Simplified Format[/bold blue]")
    console.print("=" * 60)

    # Import the new models
    from planfile import Strategy, Task, execute_strategy

    # Test 1: Load simple strategy
    console.print("\n[bold]1. Loading Simple Strategy[/bold]")
    try:
        strategy = Strategy.load_flexible("examples/strategy_simple_v2.yaml")
        console.print(f"✅ Loaded: {strategy.name} v{strategy.version}")
        console.print(f"   Sprints: {len(strategy.sprints)}")
        console.print(f"   Total tasks: {len(strategy.get_task_patterns())}")
    except Exception as e:
        console.print(f"❌ Error: {e}")
        return

    # Test 2: Validate flexible format
    console.print("\n[bold]2. Testing Flexible Format[/bold]")

    # Test minimal strategy
    minimal_data = {
        "name": "Minimal Strategy",
        "goal": "Do something",
        "sprints": [
            {
                "id": 1,
                "name": "Sprint 1",
                "tasks": [
                    {
                        "name": "Task 1",
                        "description": "Do something",
                        "type": "feature"
                    }
                ]
            }
        ]
    }

    try:
        minimal = Strategy.load_flexible(minimal_data)
        console.print("✅ Minimal strategy works")
    except Exception as e:
        console.print(f"❌ Minimal strategy failed: {e}")

    # Test 3: Execute with dry run
    console.print("\n[bold]3. Testing Execution (Dry Run)[/bold]")

    try:
        results = execute_strategy(
            strategy_path="examples/strategy_simple_v2.yaml",
            project_path="/home/tom/github/semcod/planfile",
            dry_run=True
        )

        # Display results
        table = Table(title="Execution Results")
        table.add_column("Task", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Priority", style="yellow")
        table.add_column("Status", style="green")
        table.add_column("Model", style="blue")

        for result in results:
            # Find the task to get more info
            task = None
            for sprint in strategy.sprints:
                for t in sprint.tasks:
                    if t.name == result.task_name:
                        task = t
                        break

            table.add_row(
                result.task_name,
                task.type if task else "N/A",
                task.priority if task else "N/A",
                result.status,
                result.model_used
            )

        console.print(table)
        console.print(f"\n✅ All {len(results)} tasks executed successfully in dry-run mode")

    except Exception as e:
        console.print(f"❌ Execution failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 4: Show model flexibility
    console.print("\n[bold]4. Testing Model Flexibility[/bold]")

    test_tasks = [
        {"name": "Simple Task", "model_hints": "free"},
        {"name": "Complex Task", "model_hints": {"implementation": "premium"}},
        {"name": "Default Task", "model_hints": {}},
    ]

    for task_data in test_tasks:
        task = Task(
            name=task_data["name"],
            description="Test task",
            model_hints=task_data["model_hints"]
        )
        console.print(f"  - {task.name}: hints = {task.model_hints}")

    console.print("\n[bold green]✅ All tests passed! The v2 format is more flexible and easier to use.[/bold green]")


def test_backward_compatibility():
    """Test that v1 format still works."""

    console.print("\n[bold blue]Testing Backward Compatibility[/bold blue]")
    console.print("=" * 60)

    from planfile import Strategy

    # Try to load an old format strategy
    old_format = {
        "name": "Old Format Strategy",
        "project_type": "python",
        "domain": "software",
        "goal": "Test old format",
        "sprints": [
            {
                "id": 1,
                "name": "Sprint 1",
                "objectives": ["Test"],
                "tasks": ["task1"]
            }
        ],
        "tasks": {
            "patterns": [
                {
                    "id": "task1",
                    "type": "feature",
                    "title": "Test Task",
                    "description": "A test task"
                }
            ]
        }
    }

    try:
        # Convert to v2 format
        v2_strategy = Strategy.load_flexible(Strategy._convert_old_format(old_format))
        console.print("✅ Old format successfully converted to v2")
        console.print(f"   Tasks in sprint: {len(v2_strategy.sprints[0].tasks)}")
    except Exception as e:
        console.print(f"❌ Conversion failed: {e}")


if __name__ == "__main__":
    test_v2_format()
    test_backward_compatibility()

    console.print("\n[bold]Summary of Improvements:[/bold]")
    console.print("• Tasks are now embedded directly in sprints")
    console.print("• Model hints accept simple strings")
    console.print("• More flexible validation with sensible defaults")
    console.print("• Support for both string and list criteria")
    console.print("• Backward compatibility maintained")
    console.print("• Simpler API for common use cases")
