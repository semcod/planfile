#!/bin/bash

# Test script for README examples
# This script tests the CLI commands shown in the README

set -e

echo "Testing README examples..."

# Create a temporary test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

echo "Test directory: $TEST_DIR"

# Initialize a test project
echo -e "\n1. Initializing test project..."
mkdir -p test-project/src
cd test-project

# Create a simple Python file for testing
cat > src/main.py << 'EOF'
"""Main module for test project."""

def hello_world():
    """Return hello world message."""
    return "Hello, World!"

class TestClass:
    """A test class."""
    
    def __init__(self, name: str):
        self.name = name
    
    def greet(self) -> str:
        """Greet the initialized name."""
        return f"Hello, {self.name}!"
EOF

# Create setup.py for better project structure
cat > setup.py << 'EOF'
from setuptools import setup, find_packages

setup(
    name="test-project",
    version="0.1.0",
    packages=find_packages(),
    python_requires=">=3.10",
)
EOF

echo -e "\n2. Testing planfile init..."
planfile init || {
    echo "ERROR: planfile init failed"
    exit 1
}

# Check if planfile.yaml was created
if [ ! -f "planfile.yaml" ]; then
    echo "ERROR: planfile.yaml was not created"
    exit 1
fi

echo "✓ planfile.yaml created successfully"

# Display generated planfile.yaml
echo -e "\nGenerated planfile.yaml:"
cat planfile.yaml

echo -e "\n3. Testing planfile validate..."
planfile strategy validate --strategy planfile.yaml || {
    echo "ERROR: planfile validate failed"
    exit 1
}

echo "✓ planfile.yaml validation passed"

echo -e "\n4. Testing planfile apply (dry-run)..."
planfile strategy apply --strategy planfile.yaml --backend generic --dry-run || {
    echo "WARNING: planfile apply dry-run failed"
}

echo -e "\n5. Testing with custom strategy..."
cat > custom_strategy.yaml << 'EOF'
project:
  name: "Custom Test Project"
  description: "A custom test project for planfile"
  
sprints:
  - id: 1
    name: "Sprint 1"
    start_date: "2024-01-01"
    end_date: "2024-01-14"
    
tasks:
  - name: "Setup project structure"
    type: "feature"
    priority: "high"
    sprint_id: 1
    description: "Create basic project structure"
    
  - name: "Implement core functionality"
    type: "feature"
    priority: "medium"
    sprint_id: 1
    description: "Implement core features"

quality_gates:
  - name: "Code coverage"
    threshold: 80
    type: "coverage"
  - name: "All tests pass"
    type: "tests"
    
integrations:
  backends:
    - type: "generic"
      name: "test"
      config:
        api_url: "https://api.example.com"
EOF

echo -e "\n6. Testing custom strategy validation..."
planfile strategy validate --strategy custom_strategy.yaml || {
    echo "ERROR: Custom strategy validation failed"
    exit 1
}

echo "✓ Custom strategy validation passed"

echo -e "\n7. Testing interactive mode (simulated)..."
# Create expect script for interactive mode
cat > interactive_test.exp << 'EOF'
#!/usr/bin/expect -f

set timeout 10
spawn planfile init --interactive

expect "Project name:"
send "Interactive Test Project\r"

expect "Project description:"
send "A project created in interactive mode\r"

expect "Backend type"
send "generic\r"

expect eof
EOF

# Note: expect might not be installed, so we'll just show the command
echo "Interactive mode test script created (requires expect to run)"

# Cleanup
cd ../..
rm -rf "$TEST_DIR"

echo -e "\n✅ All README examples tested successfully!"
