#!/bin/bash
set -e

echo "💻 PLANFILE CLI COMMANDS DEMO - FIXED VERSION"
echo "Demonstrating core CLI commands for handling planfile strategies."
echo "--------------------------------------------------"

# Create generic test strategy
if [ ! -f "test-strategy.yaml" ]; then
    echo "Creating generic test strategy..."
    planfile template web test --output test-strategy.yaml
fi

echo "1. Validate Configuration"
planfile validate test-strategy.yaml

echo "--------------------------------------------------"
echo "2. Review Configuration (with current directory)"
planfile review test-strategy.yaml . || echo "⚠️  Review failed, but that's OK for demo"

echo "--------------------------------------------------"
echo "3. Apply Configuration (Dry run)"
planfile apply test-strategy.yaml . --dry-run || echo "⚠️  Apply failed, but that's OK for demo"

echo "--------------------------------------------------"
echo "4. Strategy Statistics"
planfile stats test-strategy.yaml

echo "--------------------------------------------------"
echo "5. Export to JSON"
planfile export test-strategy.yaml --format json --output test-strategy.json

echo "✅ CLI COMMANDS DEMO COMPLETED!"
echo "Files created:"
ls -l *.yaml *.json 2>/dev/null || echo "No files found"
