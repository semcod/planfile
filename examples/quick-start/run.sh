#!/bin/bash
set -e

echo "⚡ PLANFILE QUICK START (CLI)"
echo "These examples will get you started with planfile in minutes using the command line!"

echo "--------------------------------------------------"
echo "1. Generate from Files"
echo "> planfile generate-from-files ../strategies --project-name example-project --max-sprints 2 --output quick-start.yaml"
planfile generate-from-files ../strategies --project-name "example-project" --max-sprints 2 --output quick-start.yaml
echo "✅ Complete!"

echo "--------------------------------------------------"
echo "2. Create Template"
echo "> planfile template web example --output web-template.yaml"
planfile template web example --output web-template.yaml
echo "✅ Complete!"

echo "--------------------------------------------------"
echo "3. Load and Analyze (Stats)"
echo "> planfile stats web-template.yaml"
planfile stats web-template.yaml
echo "✅ Complete!"

echo "--------------------------------------------------"
echo "4. Export Formats (JSON)"
echo "> planfile export web-template.yaml --format json --output web-template.json"
planfile export web-template.yaml --format json --output web-template.json
echo "✅ Complete!"

echo "--------------------------------------------------"
echo "5. Compare Strategies"
echo "> planfile compare quick-start.yaml web-template.yaml"
planfile compare quick-start.yaml web-template.yaml || true
echo "✅ Complete!"

echo "--------------------------------------------------"
echo "QUICK START COMPLETE!"
echo "Files created:"
ls -l *.yaml *.json
