#!/bin/bash
set -e

echo "💻 PLANFILE CLI COMMANDS DEMO"
echo "Demonstrating core CLI commands for handling planfile strategies."
echo "--------------------------------------------------"

# Assuming we have strategies directory in the parent
if [ ! -f "test-strategy.yaml" ]; then
    echo "Creating generic test strategy..."
    planfile template web test --output test-strategy.yaml
fi

echo "1. Validate Configuration"
planfile validate test-strategy.yaml

echo "--------------------------------------------------"
echo "2. Review Configuration"
planfile review test-strategy.yaml

echo "--------------------------------------------------"
echo "3. Apply Configuration (Dry run)"
planfile apply test-strategy.yaml . --dry-run

echo "--------------------------------------------------"
echo "4. Strategy Statistics"
planfile stats test-strategy.yaml

echo "✅ CLI COMMANDS DEMO COMPLETED!"
