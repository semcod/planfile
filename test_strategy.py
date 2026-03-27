"""
Simple test to verify the strategy package structure.
"""
from pathlib import Path

from planfile.loaders.yaml_loader import load_strategy_yaml
from planfile.models import Sprint, Strategy, TaskPattern, TaskType


def test_basic_models():
    """Test basic model creation."""
    # Create a simple strategy
    strategy = Strategy(
        name="Test Strategy",
        project_type="web",
        domain="test",
        goal="Test the strategy package",
        sprints=[
            Sprint(
                id=1,
                name="Test Sprint",
                length_days=14,
                objectives=["Test objective"],
                tasks=["test-task"]
            )
        ],
        tasks={
            "patterns": [
                TaskPattern(
                    id="test-task",
                    type=TaskType.feature,
                    title="Test Task",
                    description="A test task pattern"
                )
            ]
        }
    )

    assert strategy.name == "Test Strategy"
    assert len(strategy.sprints) == 1
    assert strategy.get_task_patterns()[0].id == "test-task"
    print("✓ Basic models work correctly")


def test_yaml_loading():
    """Test YAML loading functionality."""
    example_path = Path(__file__).parent / "examples" / "strategies" / "onboarding.yaml"

    if example_path.exists():
        strategy = load_strategy_yaml(example_path)
        assert strategy.name == "Onboarding Strategy"
        assert len(strategy.sprints) == 3
        print("✓ YAML loading works correctly")
    else:
        print("⚠ Example YAML file not found, skipping test")


if __name__ == "__main__":
    test_basic_models()
    test_yaml_loading()
    print("\nAll tests passed! 🎉")
