#!/bin/bash
# External Tools Example Runner

echo "🔧" * 20
echo "EXTERNAL TOOLS EXAMPLES"
echo "🔧" * 20
echo ""

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile not found. Install with:"
    echo "   pip install -e ."
    exit 1
fi

# Check for external tools
echo "Checking external tools..."
tools_available=false

if command -v code2llm &> /dev/null; then
    echo "  ✓ code2llm found"
    tools_available=true
else
    echo "  ⚠ code2llm not found (optional)"
    echo "    Install with: pip install code2llm"
fi

if command -v vallm &> /dev/null; then
    echo "  ✓ vallm found"
    tools_available=true
else
    echo "  ⚠ vallm not found (optional)"
    echo "    Install with: pip install vallm"
fi

if command -v redup &> /dev/null; then
    echo "  ✓ redup found"
    tools_available=true
else
    echo "  ⚠ redup not found (optional)"
    echo "    Install with: pip install redup"
fi

echo ""
if [ "$tools_available" = true ]; then
    echo "✅ Some external tools found - running full analysis"
else
    echo "⚠ No external tools found - running in demo mode"
    echo "   Install tools for full functionality"
fi

echo ""

# Run the example
python3 external_tools_examples.py

echo ""
echo "✅ External tools examples complete!"
echo ""
echo "Generated files:"
echo "  Analysis outputs:"
ls -la *.toon.yaml 2>/dev/null | grep -v "^total" || echo "    None (install tools for analysis)"
echo ""
echo "  Strategies:"
ls -la *-generated.yaml *-focused.yaml 2>/dev/null | grep -v "^total" || echo "    No strategies generated"
echo ""
echo "Next: Try 'cd ../advanced-usage && ./run.sh' for advanced patterns"
