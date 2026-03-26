#!/bin/bash

# Verify planfile.yaml correctness script
# This script validates the structure and content of generated planfile.yaml files

set -e

echo "Verifying planfile.yaml correctness..."

# Function to validate planfile.yaml
validate_planfile() {
    local file_path=$1
    
    echo -e "\nValidating: $file_path"
    
    # Check if file exists
    if [ ! -f "$file_path" ]; then
        echo "❌ File does not exist"
        return 1
    fi
    
    # Check YAML syntax
    if command -v python3 &> /dev/null; then
        python3 -c "
import yaml
import sys
try:
    with open('$file_path', 'r') as f:
        yaml.safe_load(f)
    print('✓ Valid YAML syntax')
except yaml.YAMLError as e:
    print(f'❌ YAML syntax error: {e}')
    sys.exit(1)
except Exception as e:
    print(f'❌ Error reading file: {e}')
    sys.exit(1)
"
    else
        echo "⚠️  Python3 not found, skipping YAML syntax check"
    fi
    
    # Check required top-level keys
    local required_keys=("project" "sprints" "tasks")
    for key in "${required_keys[@]}"; do
        if grep -q "^$key:" "$file_path"; then
            echo "✓ Required key '$key' found"
        else
            echo "❌ Required key '$key' missing"
            return 1
        fi
    done
    
    # Check project section
    if grep -A 5 "^project:" "$file_path" | grep -q "name:"; then
        echo "✓ Project name found"
    else
        echo "⚠️  Project name not specified"
    fi
    
    # Check sprints structure
    local sprint_count=$(grep -c "^  - id:" "$file_path" || echo "0")
    if [ "$sprint_count" -gt 0 ]; then
        echo "✓ Found $sprint_count sprint(s)"
        
        # Check if sprints have required fields
        if grep -A 2 "^  - id:" "$file_path" | grep -q "name:"; then
            echo "✓ Sprints have names"
        else
            echo "⚠️  Some sprints missing names"
        fi
    else
        echo "⚠️  No sprints defined"
    fi
    
    # Check tasks structure
    local task_count=$(grep -c "^  - name:" "$file_path" || echo "0")
    if [ "$task_count" -gt 0 ]; then
        echo "✓ Found $task_count task(s)"
        
        # Check task types
        local task_types=$(grep "^    type:" "$file_path" | sort | uniq -c || echo "No types found")
        echo "  Task types:"
        echo "$task_types"
        
        # Check priorities
        local priorities=$(grep "^    priority:" "$file_path" | sort | uniq -c || echo "No priorities found")
        echo "  Priorities:"
        echo "$priorities"
    else
        echo "⚠️  No tasks defined"
    fi
    
    # Check optional sections
    local optional_keys=("quality_gates" "integrations" "dependencies")
    for key in "${optional_keys[@]}"; do
        if grep -q "^$key:" "$file_path"; then
            echo "✓ Optional section '$key' found"
        fi
    done
    
    # Run planfile validation if available
    if command -v planfile &> /dev/null; then
        echo -e "\nRunning planfile validation..."
        if planfile strategy validate --strategy "$file_path" 2>/dev/null; then
            echo "✓ Passed planfile validation"
        else
            echo "⚠️  Failed planfile validation"
        fi
    fi
    
    return 0
}

# Test with sample planfiles
echo -e "\n=== Testing sample planfiles ==="

# Create test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

# Sample 1: Minimal valid planfile
cat > minimal.yaml << 'EOF'
project:
  name: "Minimal Project"
  
sprints:
  - id: 1
    name: "Sprint 1"
    
tasks:
  - name: "Task 1"
    type: "feature"
    priority: "medium"
EOF

# Sample 2: Complete planfile
cat > complete.yaml << 'EOF'
project:
  name: "Complete Project"
  description: "A complete example project"
  version: "1.0.0"
  
sprints:
  - id: 1
    name: "Setup"
    start_date: "2024-01-01"
    end_date: "2024-01-14"
    goal: "Initial setup"
  - id: 2
    name: "Development"
    start_date: "2024-01-15"
    end_date: "2024-01-28"
    goal: "Core features"
    
tasks:
  - name: "Setup repository"
    type: "feature"
    priority: "high"
    sprint_id: 1
    description: "Initialize git repository"
    estimated_hours: 2
    
  - name: "Implement authentication"
    type: "feature"
    priority: "high"
    sprint_id: 2
    description: "Add user authentication"
    dependencies:
      - "Setup repository"
    estimated_hours: 16
    
  - name: "Fix login bug"
    type: "bug"
    priority: "critical"
    sprint_id: 1
    description: "Fix login page issue"
    
quality_gates:
  - name: "Test coverage"
    threshold: 80
    type: "coverage"
    description: "Minimum 80% test coverage"
    
  - name: "All tests pass"
    type: "tests"
    description: "All unit and integration tests must pass"
    
integrations:
  backends:
    - type: "github"
      name: "github"
      config:
        repo: "org/repo"
        token: "${GITHUB_TOKEN}"
        
    - type: "jira"
      name: "jira"
      config:
        url: "https://company.atlassian.net"
        username: "${JIRA_USERNAME}"
        api_token: "${JIRA_TOKEN}"
        
dependencies:
  python:
    - "pydantic>=2.0"
    - "typer>=0.12"
  system:
    - "python>=3.10"
EOF

# Sample 3: Invalid planfile
cat > invalid.yaml << 'EOF'
project:
  # Missing name
  
sprints:
  - id: 1
    # Missing name
    
tasks:
  - name: "Task"
    # Missing type and priority
    
invalid_key:
  sub_key: "value"
  
  - item1
  - item2
EOF

# Validate all samples
echo -e "\n--- Minimal Planfile ---"
validate_planfile minimal.yaml

echo -e "\n--- Complete Planfile ---"
validate_planfile complete.yaml

echo -e "\n--- Invalid Planfile ---"
validate_planfile invalid.yaml || echo "Expected validation failure for invalid file"

# Cleanup
cd ..
rm -rf "$TEST_DIR"

echo -e "\n✅ Planfile verification completed!"
