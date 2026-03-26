#!/bin/bash
# Quick Start Example Runner

echo "⚡" * 20
echo "PLANFILE QUICK START"
echo "⚡" * 20
echo ""

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile not found. Install with:"
    echo "   pip install -e ."
    exit 1
fi

# Run the example
python3 quick_start_examples.py

echo ""
echo "✅ Quick start complete!"
echo ""
echo "Generated files:"
ls -la *.yaml *.json 2>/dev/null | grep -v "^total" || echo "  No files generated"
echo ""
echo "Next: Try 'cd ../integrated-functionality && ./run.sh' for more examples"
