#!/bin/bash
# CI/CD Planfile Workflow

echo "Running planfile analysis..."
python3 -m planfile.cli.commands generate-from-files . --focus quality --output ci-strategy.yaml

echo "Validating strategy..."
python3 -m planfile.cli.commands validate ci-strategy.yaml

echo "Checking project health..."
python3 -m planfile.cli.commands health . --output ci-health.json

echo "Exporting report..."
python3 -m planfile.cli.commands export ci-strategy.yaml --format html --output ci-report.html

echo "Workflow complete!"
