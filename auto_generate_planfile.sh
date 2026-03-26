#!/bin/bash
# Automated Planfile Generation Script
# Runs analysis tools and generates planfile.yaml

set -e

echo "============================================================"
echo "AUTOMATED PLANFILE GENERATION ALGORITHM"
echo "============================================================"

# Configuration
PROJECT_PATH="${1:-.}"
OUTPUT_DIR="${PROJECT_PATH}/project"
VENV_PATH="${PROJECT_PATH}/venv"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Run from project root."
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo ""
echo "🔍 STEP 1: Running code2llm analysis..."
echo "------------------------------------------------------------"

if [ -f "$VENV_PATH/bin/code2llm" ]; then
    "$VENV_PATH/bin/code2llm" "$PROJECT_PATH" -f all -o "$OUTPUT_DIR" --no-chunk
    echo "✅ code2llm completed"
else
    echo "⚠️  code2llm not found at $VENV_PATH/bin/code2llm"
    echo "   Install with: pip install code2llm"
fi

echo ""
echo "🔍 STEP 2: Running vallm validation..."
echo "------------------------------------------------------------"

if [ -f "$VENV_PATH/bin/vallm" ]; then
    "$VENV_PATH/bin/vallm" batch "$PROJECT_PATH" --recursive --format toon --output "$OUTPUT_DIR"
    echo "✅ vallm completed"
else
    echo "⚠️  vallm not found at $VENV_PATH/bin/vallm"
    echo "   Install with: pip install vallm"
fi

echo ""
echo "🔍 STEP 3: Running redup analysis..."
echo "------------------------------------------------------------"

if [ -f "$VENV_PATH/bin/redup" ]; then
    "$VENV_PATH/bin/redup" scan "$PROJECT_PATH" --format toon --output "$OUTPUT_DIR"
    echo "✅ redup completed"
else
    echo "⚠️  redup not found at $VENV_PATH/bin/redup"
    echo "   Install with: pip install redup"
fi

echo ""
echo "📝 STEP 4: Generating planfile..."
echo "------------------------------------------------------------"

# Run the Python generator
python3 generate_planfile.py --project-path "$PROJECT_PATH"

echo ""
echo "✅ GENERATION COMPLETE!"
echo "============================================================"

# Show summary if files exist
if [ -f "$OUTPUT_DIR/analysis.toon.yaml" ]; then
    echo ""
    echo "📊 ANALYSIS SUMMARY:"
    echo "-------------------"
    
    # Extract CC average
    CC_AVG=$(grep "CC̄=" "$OUTPUT_DIR/analysis.toon.yaml" | head -1 | sed 's/.*CC̄=\([0-9.]*\).*/\1/')
    echo "Average CC: $CC_AVG"
    
    # Extract critical functions
    CRITICAL=$(grep "critical:" "$OUTPUT_DIR/analysis.toon.yaml" | head -1 | sed 's/.*critical:\([0-9]*\).*/\1/')
    echo "Critical functions: $CRITICAL"
fi

if [ -f "$OUTPUT_DIR/validation.toon.yaml" ]; then
    # Extract validation stats
    ERRORS=$(grep "errors:" "$OUTPUT_DIR/validation.toon.yaml" | head -1 | sed 's/.*errors: \([0-9]*\).*/\1/')
    WARNINGS=$(grep "warnings:" "$OUTPUT_DIR/validation.toon.yaml" | head -1 | sed 's/.*warnings: \([0-9]*\).*/\1/')
    echo "Validation errors: $ERRORS"
    echo "Validation warnings: $WARNINGS"
fi

if [ -f "$OUTPUT_DIR/duplication.toon.yaml" ]; then
    # Extract duplication stats
    DUP_GROUPS=$(grep "dup_groups:" "$OUTPUT_DIR/duplication.toon.yaml" | head -1 | sed 's/.*dup_groups: \([0-9]*\).*/\1/')
    echo "Duplication groups: $DUP_GROUPS"
fi

echo ""
echo "📄 Generated files:"
echo "  - planfile.yaml (generated strategy)"
echo "  - project/ (analysis results)"

# Validate generated planfile
if [ -f "planfile.yaml" ]; then
    echo ""
echo "🔍 STEP 5: Validating generated planfile..."
    echo "------------------------------------------------------------"
    
    if python3 -m planfile.cli.commands validate planfile.yaml; then
        echo "✅ Generated planfile is valid!"
    else
        echo "❌ Generated planfile has validation issues"
    fi
fi

echo ""
echo "Next steps:"
echo "1. Review generated planfile.yaml"
echo "2. Adjust priorities and estimates as needed"
echo "3. Execute: python3 -m planfile.cli.commands apply planfile.yaml . --dry-run"
echo "4. Create tickets in your project management tool"
