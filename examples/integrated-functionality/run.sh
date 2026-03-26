#!/bin/bash
# Integrated Functionality Example Runner

echo "🚀" * 20
echo "INTEGRATED FUNCTIONALITY EXAMPLES"
echo "🚀" * 20
echo ""

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile not found. Install with:"
    echo "   pip install -e ."
    exit 1
fi

# Check for optional external tools
echo "🔧 Checking for external tools..."
if command -v code2llm &> /dev/null; then
    echo "  ✓ code2llm found"
else
    echo "  ⚠ code2llm not found (optional)"
fi

if command -v vallm &> /dev/null; then
    echo "  ✓ vallm found"
else
    echo "  ⚠ vallm not found (optional)"
fi

if command -v redup &> /dev/null; then
    echo "  ✓ redup found"
else
    echo "  ⚠ redup not found (optional)"
fi

echo ""
echo "Running integrated functionality examples..."
echo ""

# Run the example
python3 integrated_functionality_examples.py

echo ""
echo "✅ Integrated functionality examples complete!"
echo ""
echo "Generated files:"
echo "  Strategies:"
ls -la *-strategy.yaml *-template.yaml 2>/dev/null | grep -v "^total" || echo "    No strategy files"
echo ""
echo "  Exports:"
ls -la *-export.* 2>/dev/null | grep -v "^total" || echo "    No export files"
echo ""
echo "Next: Try 'cd ../cli-commands && ./run.sh' for CLI examples"
