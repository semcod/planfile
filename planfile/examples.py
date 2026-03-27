"""
Example usage of LLX strategy integration.
"""
from pathlib import Path


# Example 1: Create strategy interactively
def example_create_strategy() -> None:
    """Create a strategy using LLX with local LLM."""
    from llx.planfile import create_strategy_command

    # This will prompt user interactively
    create_strategy_command(
        output="my_strategy.yaml",
        model="qwen2.5:3b",
        local=True
    )


# Example 2: Load and validate strategy
def example_validate_strategy() -> None:
    """Load and validate an existing strategy."""
    from llx.planfile import load_valid_strategy

    try:
        strategy = load_valid_strategy("my_strategy.yaml")
        print(f"Strategy '{strategy.name}' is valid!")
        print(f"Sprints: {len(strategy.sprints)}")
    except Exception as e:
        print(f"Invalid strategy: {e}")


# Example 3: Run strategy (dry run)
def example_run_strategy() -> None:
    """Run strategy to create tickets (dry run)."""
    from llx.planfile import run_strategy

    run_strategy(
        strategy_path="my_strategy.yaml",
        project_path=".",
        backend="github",
        dry_run=True  # Set to False to actually create tickets
    )


# Example 4: Verify strategy after execution
def example_verify_strategy() -> None:
    """Verify strategy execution."""
    from llx.planfile import load_valid_strategy, verify_strategy_post_execution

    strategy = load_valid_strategy("my_strategy.yaml")
    issues = verify_strategy_post_execution(
        strategy=strategy,
        project_path=".",
        backend="github"
    )

    if issues:
        print("Issues found:", issues)
    else:
        print("Strategy executed successfully!")


# Example 5: Programmatic strategy creation
def example_programmatic_strategy() -> None:
    """Create strategy programmatically without LLM."""
    from llx.planfile.models import Goal, ModelHints, Sprint, Strategy, TaskPattern, TaskType

    # Create goal
    goal = Goal(
        short="Build a REST API for user management",
        quality=["Test coverage > 90%", "All endpoints documented"],
        delivery=["Deploy to staging in 2 weeks", "Production ready in 4 weeks"]
    )

    # Create task patterns
    patterns = [
        TaskPattern(
            id="api_endpoint",
            type=TaskType.feature,
            title="Implement {endpoint} endpoint",
            description="Create REST endpoint for {endpoint} with:\n- Request validation\n- Error handling\n- Response formatting\n- Unit tests",
            model_hints=ModelHints(
                design="balanced",
                implementation="balanced"
            )
        ),
        TaskPattern(
            id="api_bug",
            type=TaskType.bug,
            title="Fix: {issue_description}",
            description="Bug report:\n- Description: {issue_description}\n- Steps to reproduce: {reproduction_steps}\n- Expected behavior: {expected_behavior}",
            priority="high"
        )
    ]

    # Create sprints
    sprints = [
        Sprint(
            id=1,
            name="Core API",
            objectives=["User authentication", "CRUD operations"],
            tasks=["api_endpoint"]
        ),
        Sprint(
            id=2,
            name="Advanced Features",
            objectives=["Rate limiting", "API documentation"],
            tasks=["api_endpoint"]
        )
    ]

    # Create strategy
    strategy = Strategy(
        name="User Management API",
        project_type="api",
        domain="backend",
        goal=goal,
        sprints=sprints,
        tasks={"patterns": patterns}
    )

    # Save to YAML
    output = Path("programmatic_strategy.yaml")
    output.write_text(strategy.model_dump_yaml())
    print(f"Strategy saved to {output}")


if __name__ == "__main__":
    # Run examples
    print("LLX Strategy Integration Examples")
    print("=" * 40)

    # Uncomment to run examples
    # example_create_strategy()
    # example_validate_strategy()
    # example_run_strategy()
    # example_verify_strategy()
    example_programmatic_strategy()
