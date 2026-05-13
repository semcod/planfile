"""DSL usage via planfile REST API examples."""

import requests


def example_dsl_command():
    """Execute a DSL command via REST API."""
    response = requests.post(
        "http://localhost:8000/dsl",
        json={"command": "list tickets sprint=current status=open", "project_path": "."},
    )
    result = response.json()
    print(result)


def example_dsl_create_ticket():
    """Create a ticket via DSL endpoint."""
    response = requests.post(
        "http://localhost:8000/dsl",
        json={
            "command": 'create ticket "Fix login bug" priority=high sprint=1',
            "project_path": ".",
        },
    )
    result = response.json()
    print(result)


def example_dsl_update_ticket():
    """Update ticket via DSL endpoint."""
    response = requests.post(
        "http://localhost:8000/dsl",
        json={"command": "update ticket PLF-001 status=done", "project_path": "."},
    )
    result = response.json()
    print(result)


def example_dsl_sprint():
    """List and add sprints via DSL."""
    # List sprints
    response = requests.post(
        "http://localhost:8000/dsl", json={"command": "list sprints", "project_path": "."}
    )
    print(response.json())

    # Add sprint
    response = requests.post(
        "http://localhost:8000/dsl",
        json={"command": 'add sprint "Sprint 4" days=14', "project_path": "."},
    )
    print(response.json())


def example_dsl_validate_sync():
    """Validate and sync via DSL."""
    # Validate
    response = requests.post(
        "http://localhost:8000/dsl", json={"command": "validate", "project_path": "."}
    )
    print(response.json())

    # Sync to GitHub
    response = requests.post(
        "http://localhost:8000/dsl", json={"command": "sync github", "project_path": "."}
    )
    print(response.json())


def example_dsl_help():
    """Get DSL command reference."""
    response = requests.get("http://localhost:8000/dsl/help")
    print(response.json())


def example_yaml_operations():
    """Direct YAML operations via REST API."""
    # Read full YAML
    response = requests.get("http://localhost:8000/yaml")
    print(response.json())

    # Patch a value
    response = requests.patch(
        "http://localhost:8000/yaml", json={"path": "metadata.model_tier", "value": "premium"}
    )
    print(response.json())


if __name__ == "__main__":
    print("REST API DSL Examples")
    print("=" * 40)
    print("Start the server first: uvicorn planfile.api.server:app --reload")

    # Uncomment to run examples
    # example_dsl_command()
    # example_dsl_create_ticket()
    # example_dsl_update_ticket()
    # example_dsl_sprint()
    # example_dsl_validate_sync()
    # example_dsl_help()
    # example_yaml_operations()
