#!/bin/bash
set -e

echo "🚀 PLANFILE INTEGRATED FUNCTIONALITY (CLI)"

echo "--------------------------------------------------"
echo "1. Generate from Files (with focus)"
planfile generate-from-files ../strategies --project-name "planfile-core" --focus quality --max-sprints 2 --output generated.yaml

echo "--------------------------------------------------"
echo "2. Generate Templates for Multiple Domains"
planfile template web ecommerce --output web-ecommerce.yaml
planfile template mobile healthcare --output mobile-healthcare.yaml
planfile template ml finance --output ml-finance.yaml

echo "--------------------------------------------------"
echo "3. Compare Strategies"
planfile compare web-ecommerce.yaml mobile-healthcare.yaml || true

echo "--------------------------------------------------"
echo "4. Export Formats"
planfile export web-ecommerce.yaml --format json --output web.json
planfile export web-ecommerce.yaml --format html --output web.html
planfile export web-ecommerce.yaml --format csv --output web.csv

echo "--------------------------------------------------"
echo "5. Strategy Statistics"
planfile stats web-ecommerce.yaml

echo "--------------------------------------------------"
echo "6. Merge Strategies"
planfile merge web-ecommerce.yaml mobile-healthcare.yaml ml-finance.yaml --name "Merged Multi-Domain" --output merged.yaml

echo "--------------------------------------------------"
echo "7. External Tools (if available)"
planfile generate-from-files ../../ --project-name "planfile-external" --external-tools --output external.yaml || true

echo "✅ ALL EXAMPLES COMPLETED!"
