#!/bin/bash
set -e

echo "🔧 PLANFILE EXTERNAL TOOLS BASH DEMO"
echo "This demonstrates how to use the CLI with external tools like code2llm, vallm, and redup."

# Using the new --external-tools flag with --compact to reduce file size
planfile generate-from-files ../../ --project-name "planfile-analysis" --focus security --external-tools --compact --output full-analysis.yaml

echo "Checking output:"
ls -lh full-analysis.yaml
echo "✅ Complete!"
