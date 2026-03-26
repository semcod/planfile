#!/bin/bash
# CLI Commands Example Runner

echo "💻" * 20
echo "CLI COMMANDS EXAMPLES"
echo "💻" * 20
echo ""

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile not found. Install with:"
    echo "   pip install -e ."
    exit 1
fi

# Check if CLI is available
if ! python3 -m planfile.cli.commands --help &> /dev/null; then
    echo "❌ planfile CLI not available"
    exit 1
fi

echo "Available commands:"
python3 -m planfile.cli.commands --help | grep -A 20 "Commands:" | tail -n +2
echo ""

# Run the example
python3 cli_command_examples.py

echo ""
echo "✅ CLI commands examples complete!"
echo ""
echo "Generated files:"
ls -la cli-example-* 2>/dev/null | grep -v "^total" || echo "  No files generated"
echo ""
echo "Try these commands manually:"
echo "  planfile template web myproject"
echo "  planfile stats cli-example-web.yaml"
echo "  planfile export cli-example-web.yaml --format html"
echo ""
echo "Next: Try 'cd ../external-tools && ./run.sh' for external tools examples"
