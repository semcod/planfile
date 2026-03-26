#!/bin/bash
set -e

echo "🔧 PLANFILE EXTERNAL TOOLS BASH DEMO"
echo "This demonstrates how to use the CLI with external tools like code2llm, vallm, and redup."

# Using the new --external-tools flag added to the CLI
planfile generate-from-files ../../ --project-name "planfile-analysis" --focus security --external-tools --output full-analysis.yaml

echo "Checking output:"
ls -lh full-analysis.yaml
echo "✅ Complete!"
