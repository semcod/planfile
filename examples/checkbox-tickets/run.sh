#!/bin/bash
# Convenience script to run the checkbox tickets demo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================="
echo "Planfile Checkbox Tickets Demo"
echo "========================================="
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 not found"
    exit 1
fi

# Run the demo
echo "🐍 Running Python demo..."
echo ""
python3 demo.py

echo ""
echo "========================================="
echo "Demo completed!"
echo "========================================="
echo ""
echo "Next steps:"
echo "  1. Edit TODO.md to add your own tickets"
echo "  2. Run: planfile sync markdown"
echo "  3. Check out other examples in examples/"
echo ""
