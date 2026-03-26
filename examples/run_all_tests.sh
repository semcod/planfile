#!/bin/bash

# Test runner script for all examples
# Executes all test scripts in the examples directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}PLANFILE EXAMPLES TEST SUITE${NC}"
echo -e "${BLUE}========================================${NC}"

# Function to run a test and report result
run_test() {
    local test_name=$1
    local test_script=$2
    local test_dir=$(dirname "$test_script")
    
    echo -e "\n${YELLOW}Running: $test_name${NC}"
    echo "Script: $test_script"
    echo "----------------------------------------"
    
    # Create a log file for this test
    local log_file="$test_dir/test_$(basename "$test_script" .sh).log"
    
    # Run the test and capture output
    if bash "$test_script" 2>&1 | tee "$log_file"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        echo "Check log file: $log_file"
        return 1
    fi
}

# Function to run a Python test
run_python_test() {
    local test_name=$1
    local test_script=$2
    local test_dir=$(dirname "$test_script")
    
    echo -e "\n${YELLOW}Running: $test_name${NC}"
    echo "Script: $test_script"
    echo "----------------------------------------"
    
    # Create a log file for this test
    local log_file="$test_dir/test_$(basename "$test_script" .py).log"
    
    # Run the test and capture output
    if python3 "$test_script" 2>&1 | tee "$log_file"; then
        echo -e "${GREEN}✓ PASSED: $test_name${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED: $test_name${NC}"
        echo "Check log file: $log_file"
        return 1
    fi
}

# Track results
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Check if planfile command is available
echo -e "\n${BLUE}Checking prerequisites...${NC}"
if ! command -v planfile &> /dev/null; then
    echo -e "${RED}❌ planfile command not found. Please install planfile first.${NC}"
    echo "Installation instructions:"
    echo "  pip install -e . (from project root)"
    exit 1
fi
echo -e "${GREEN}✓ planfile command found${NC}"

# Check for optional dependencies
if command -v expect &> /dev/null; then
    echo -e "${GREEN}✓ expect command found (for interactive tests)${NC}"
else
    echo -e "${YELLOW}⚠ expect command not found (some interactive tests will be skipped)${NC}"
fi

# Test 1: README Examples
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUITE 1: README Examples${NC}"
echo -e "${BLUE}========================================${NC}"

readme_test="$EXAMPLES_DIR/readme-tests/test_readme_examples.sh"
if [ -f "$readme_test" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_test "README Examples Test" "$readme_test"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "${YELLOW}⚠ README test not found: $readme_test${NC}"
fi

# Test 2: Planfile Generation
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUITE 2: Planfile Generation${NC}"
echo -e "${BLUE}========================================${NC}"

generation_test="$EXAMPLES_DIR/bash-generation/test_planfile_generation.sh"
if [ -f "$generation_test" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_test "Planfile Generation Test" "$generation_test"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Generation test not found: $generation_test${NC}"
fi

# Test 3: Planfile Verification
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUITE 3: Planfile Verification${NC}"
echo -e "${BLUE}========================================${NC}"

verify_test="$EXAMPLES_DIR/bash-generation/verify_planfile.sh"
if [ -f "$verify_test" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_test "Planfile Verification Test" "$verify_test"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Verification test not found: $verify_test${NC}"
fi

# Test 4: Interactive Mode (Python)
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUITE 4: Interactive Mode (Python)${NC}"
echo -e "${BLUE}========================================${NC}"

interactive_python="$EXAMPLES_DIR/interactive-tests/test_interactive_mode.py"
if [ -f "$interactive_python" ]; then
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    if run_python_test "Interactive Mode Python Test" "$interactive_python"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
else
    echo -e "${YELLOW}⚠ Interactive Python test not found: $interactive_python${NC}"
fi

# Test 5: Interactive Mode (Expect)
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUITE 5: Interactive Mode (Expect)${NC}"
echo -e "${BLUE}========================================${NC}"

if command -v expect &> /dev/null; then
    interactive_expect="$EXAMPLES_DIR/interactive-tests/test_interactive_expect.sh"
    if [ -f "$interactive_expect" ]; then
        TOTAL_TESTS=$((TOTAL_TESTS + 1))
        if run_test "Interactive Mode Expect Test" "$interactive_expect"; then
            PASSED_TESTS=$((PASSED_TESTS + 1))
        else
            FAILED_TESTS=$((FAILED_TESTS + 1))
        fi
    else
        echo -e "${YELLOW}⚠ Interactive Expect test not found: $interactive_expect${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Skipping interactive expect test (expect not installed)${NC}"
fi

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${BLUE}TEST SUMMARY${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "\n${GREEN}✅ ALL TESTS PASSED!${NC}"
    exit 0
else
    echo -e "\n${RED}❌ SOME TESTS FAILED${NC}"
    echo -e "\nTo run individual tests:"
    for test_dir in "$EXAMPLES_DIR"/*; do
        if [ -d "$test_dir" ]; then
            echo "  $test_dir/"
            ls -1 "$test_dir"/*.sh "$test_dir"/*.py 2>/dev/null | sed 's/^/    /'
        fi
    done
    exit 1
fi
