#!/bin/bash

# Unified Planfile Examples Runner
# This script runs all planfile examples with proper error handling and setup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLES_DIR="$SCRIPT_DIR/examples"

# Function to print colored output
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_step() {
    echo -e "\n${YELLOW}➡️  $1${NC}"
    echo "----------------------------------------"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

# Function to run an example with error handling
run_example() {
    local example_name=$1
    local example_dir=$2
    local run_script="$example_dir/run.sh"
    local fixed_script="$example_dir/run_fixed.sh"
    
    print_step "Running $example_name"
    
    # Prefer fixed version if available
    if [ -f "$fixed_script" ]; then
        run_script="$fixed_script"
        print_info "Using fixed version: run_fixed.sh"
    elif [ ! -f "$run_script" ]; then
        print_error "Run script not found: $run_script"
        return 1
    fi
    
    # Change to example directory
    cd "$example_dir"
    
    # Make sure script is executable
    chmod +x "$(basename "$run_script")"
    
    # Run the example with error handling
    if bash "$(basename "$run_script")" 2>&1; then
        print_success "$example_name completed successfully"
        cd "$SCRIPT_DIR"
        return 0
    else
        print_error "$example_name failed"
        cd "$SCRIPT_DIR"
        return 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    print_header "CHECKING PREREQUISITES"
    
    # Check if planfile command is available
    if ! command -v planfile &> /dev/null; then
        print_error "planfile command not found. Installing..."
        pip install -e .
        if ! command -v planfile &> /dev/null; then
            print_error "Failed to install planfile. Please run: pip install -e ."
            exit 1
        fi
    fi
    print_success "planfile command found"
    
    # Check Python version
    python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_info "Python version: $python_version"
    
    # Check optional dependencies
    if command -v expect &> /dev/null; then
        print_success "expect command found (for interactive tests)"
    else
        print_info "expect command not found (some interactive tests will be skipped)"
    fi
}

# Function to setup test environment
setup_environment() {
    print_header "SETTING UP ENVIRONMENT"
    
    # Create strategies directory if it doesn't exist
    if [ ! -d "$SCRIPT_DIR/strategies" ]; then
        print_info "Creating strategies directory..."
        mkdir -p "$SCRIPT_DIR/strategies"
    fi
    
    # Create a basic strategy file for testing
    if [ ! -f "$SCRIPT_DIR/strategies/.planfile_analysis" ]; then
        print_info "Creating test analysis file..."
        cat > "$SCRIPT_DIR/strategies/.planfile_analysis" << EOF
project:
  name: "test-project"
  type: "web"
  total_files: 10
  python_files: 5
  complexity_score: 3.5
  
files:
  - path: "test.py"
    type: "python"
    complexity: 3
    lines: 50
EOF
    fi
}

# Function to run all examples
run_all_examples() {
    print_header "RUNNING ALL EXAMPLES"
    
    local total_examples=0
    local passed_examples=0
    local failed_examples=0
    
    # List of examples to run
    declare -a examples=(
        "quick-start:⚡ Quick Start Guide"
        "cli-commands:💻 CLI Commands Demo"
        "integrated-functionality:🚀 Integrated Functionality"
        "external-tools:🔧 External Tools Integration"
        "advanced-usage:🎯 Advanced Usage Patterns"
        "comprehensive-example:📚 Comprehensive Example"
    )
    
    for example in "${examples[@]}"; do
        IFS=':' read -r example_dir example_name <<< "$example"
        
        total_examples=$((total_examples + 1))
        
        if run_example "$example_name" "$EXAMPLES_DIR/$example_dir"; then
            passed_examples=$((passed_examples + 1))
        else
            failed_examples=$((failed_examples + 1))
        fi
    done
    
    # Print summary
    print_header "EXAMPLES SUMMARY"
    echo "Total examples: $total_examples"
    echo -e "${GREEN}Passed: $passed_examples${NC}"
    echo -e "${RED}Failed: $failed_examples${NC}"
    
    if [ $failed_examples -eq 0 ]; then
        print_success "ALL EXAMPLES PASSED!"
        return 0
    else
        print_error "SOME EXAMPLES FAILED"
        return 1
    fi
}

# Function to run specific example
run_specific_example() {
    local example_name=$1
    
    print_header "RUNNING SPECIFIC EXAMPLE: $example_name"
    
    if [ -d "$EXAMPLES_DIR/$example_name" ]; then
        run_example "$example_name" "$EXAMPLES_DIR/$example_name"
    else
        print_error "Example not found: $example_name"
        echo "Available examples:"
        for dir in "$EXAMPLES_DIR"/*/; do
            if [ -f "$dir/run.sh" ]; then
                basename "$dir"
            fi
        done
        return 1
    fi
}

# Function to show usage
show_usage() {
    echo "Planfile Examples Runner"
    echo "========================"
    echo ""
    echo "Usage: $0 [OPTIONS] [EXAMPLE_NAME]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -l, --list          List available examples"
    echo "  -c, --check         Check prerequisites only"
    echo "  -s, --setup         Setup environment only"
    echo ""
    echo "Examples:"
    echo "  $0                  Run all examples"
    echo "  $0 quick-start      Run quick-start example only"
    echo "  $0 cli-commands     Run cli-commands example only"
    echo ""
    echo "Available examples:"
    for dir in "$EXAMPLES_DIR"/*/; do
        if [ -f "$dir/run.sh" ]; then
            example=$(basename "$dir")
            echo "  - $example"
        fi
    done
}

# Function to list available examples
list_examples() {
    print_header "AVAILABLE EXAMPLES"
    
    for dir in "$EXAMPLES_DIR"/*/; do
        if [ -f "$dir/run.sh" ]; then
            example=$(basename "$dir")
            readme_file="$dir/README.md"
            
            if [ -f "$readme_file" ]; then
                # Get first line from README
                description=$(head -n 1 "$readme_file" | sed 's/^# //')
            else
                description="No description available"
            fi
            
            echo -e "${CYAN}$example${NC}"
            echo "  $description"
            echo ""
        fi
    done
}

# Main script logic
main() {
    case "${1:-}" in
        -h|--help)
            show_usage
            exit 0
            ;;
        -l|--list)
            list_examples
            exit 0
            ;;
        -c|--check)
            check_prerequisites
            exit 0
            ;;
        -s|--setup)
            setup_environment
            exit 0
            ;;
        "")
            check_prerequisites
            setup_environment
            run_all_examples
            ;;
        *)
            check_prerequisites
            setup_environment
            run_specific_example "$1"
            ;;
    esac
}

# Run main function with all arguments
main "$@"
