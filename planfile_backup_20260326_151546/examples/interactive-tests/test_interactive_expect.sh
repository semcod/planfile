#!/bin/bash

# Expect script for testing interactive mode
# This script automates interactive input for testing

# Check if expect is available
if ! command -v expect &> /dev/null; then
    echo "⚠️  expect is not installed. Install with:"
    echo "  Ubuntu/Debian: sudo apt-get install expect"
    echo "  macOS: brew install expect"
    echo "  RHEL/CentOS: sudo yum install expect"
    exit 1
fi

echo "Testing interactive mode with expect..."

# Create test directory
TEST_DIR=$(mktemp -d)
cd "$TEST_DIR"

# Test 1: Basic interactive mode
echo -e "\n=== Test 1: Basic interactive mode ==="

cat > basic_test.exp << 'EOF'
#!/usr/bin/expect -f
set timeout 10
spawn planfile init --interactive

expect "Project name:"
send "Basic Test Project\r"

expect "Project description:"
send "A basic test project\r"

expect "Backend type"
send "generic\r"

expect "Add custom sprints?"
send "n\r"

expect "Add custom tasks?"
send "n\r"

expect "Add quality gates?"
send "n\r"

expect "Add integrations?"
send "n\r"

expect eof
EOF

chmod +x basic_test.exp
./basic_test.exp

# Check result
if [ -f "planfile.yaml" ]; then
    echo "✓ Basic interactive test passed"
    echo "Generated planfile.yaml:"
    cat planfile.yaml
else
    echo "❌ Basic interactive test failed - no planfile.yaml generated"
fi

# Test 2: Interactive with custom data
echo -e "\n=== Test 2: Interactive with custom data ==="
mkdir custom_test
cd custom_test

cat > custom_test.exp << 'EOF'
#!/usr/bin/expect -f
set timeout 10
spawn planfile init --interactive

expect "Project name:"
send "Custom Interactive Project\r"

expect "Project description:"
send "Project with custom sprints and tasks\r"

expect "Backend type"
send "github\r"

expect "Add custom sprints?"
send "y\r"

expect "Number of sprints:"
send "2\r"

expect "Sprint 1 name:"
send "Setup Sprint\r"

expect "Sprint 1 start date"
send "2024-01-01\r"

expect "Sprint 1 end date"
send "2024-01-07\r"

expect "Sprint 1 goal"
send "Initial setup\r"

expect "Sprint 2 name:"
send "Development Sprint\r"

expect "Sprint 2 start date"
send "2024-01-08\r"

expect "Sprint 2 end date"
send "2024-01-14\r"

expect "Sprint 2 goal"
send "Core development\r"

expect "Add custom tasks?"
send "y\r"

expect "Number of tasks:"
send "3\r"

expect "Task 1 name:"
send "Create repository\r"

expect "Task 1 type:"
send "feature\r"

expect "Task 1 priority:"
send "high\r"

expect "Task 1 sprint ID:"
send "1\r"

expect "Task 2 name:"
send "Setup CI/CD\r"

expect "Task 2 type:"
send "feature\r"

expect "Task 2 priority:"
send "medium\r"

expect "Task 2 sprint ID:"
send "1\r"

expect "Task 3 name:"
send "Implement feature\r"

expect "Task 3 type:"
send "feature\r"

expect "Task 3 priority:"
send "high\r"

expect "Task 3 sprint ID:"
send "2\r"

expect "Add quality gates?"
send "y\r"

expect "Number of quality gates:"
send "2\r"

expect "Gate 1 name:"
send "Code Coverage\r"

expect "Gate 1 type:"
send "coverage\r"

expect "Gate 1 threshold:"
send "80\r"

expect "Gate 2 name:"
send "All Tests Pass\r"

expect "Gate 2 type:"
send "tests\r"

expect "Gate 2 threshold:"
send "100\r"

expect "Add integrations?"
send "y\r"

expect "Number of backends:"
send "1\r"

expect "Backend 1 type:"
send "github\r"

expect "Backend 1 name:"
send "github\r"

expect eof
EOF

chmod +x custom_test.exp
./custom_test.exp

# Check result
if [ -f "planfile.yaml" ]; then
    echo "✓ Custom interactive test passed"
    
    # Verify content
    if grep -q "Custom Interactive Project" planfile.yaml; then
        echo "✓ Project name set correctly"
    fi
    
    sprint_count=$(grep -c "^  - id:" planfile.yaml || echo "0")
    task_count=$(grep -c "^  - name:" planfile.yaml || echo "0")
    gate_count=$(grep -c "^  - name:" planfile.yaml | grep -v "sprint\|task" || echo "0")
    
    echo "✓ Generated $sprint_count sprints, $task_count tasks, $gate_count quality gates"
    
    echo -e "\nGenerated planfile.yaml:"
    cat planfile.yaml
else
    echo "❌ Custom interactive test failed - no planfile.yaml generated"
fi

# Test 3: Repeat generation test
echo -e "\n=== Test 3: Repeat generation test ==="
cd ..
mkdir repeat_test
cd repeat_test

# Run the same command twice to test consistency
cat > repeat_test.exp << 'EOF'
#!/usr/bin/expect -f
set timeout 10
spawn planfile init --interactive

expect "Project name:"
send "Repeat Test Project\r"

expect "Project description:"
send "Testing repeat generation\r"

expect "Backend type"
send "generic\r"

expect "Add custom sprints?"
send "n\r"

expect "Add custom tasks?"
send "n\r"

expect "Add quality gates?"
send "n\r"

expect "Add integrations?"
send "n\r"

expect eof
EOF

chmod +x repeat_test.exp

# First run
./repeat_test.exp
cp planfile.yaml planfile.yaml.first

# Second run
rm planfile.yaml
./repeat_test.exp

# Compare
if diff planfile.yaml planfile.yaml.first > /dev/null; then
    echo "✓ Generation is repeatable - files are identical"
else
    echo "⚠️  Generation differs between runs"
    echo "Differences:"
    diff planfile.yaml planfile.yaml.first || true
fi

# Cleanup
cd ../..
rm -rf "$TEST_DIR"

echo -e "\n✅ All interactive mode tests completed!"
