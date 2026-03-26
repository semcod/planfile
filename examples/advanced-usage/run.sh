#!/bin/bash
set -e

echo "🛠 PLANFILE ADVANCED USAGE PIPELINE (CLI)"
echo "This demonstrates using planfile in a bash-based automated pipeline workflow."

echo "--------------------------------------------------"
echo "[Pipeline Phase 1] Lint and Code Generation"
# In a real CI, this might fail the build if it finds critical issues
planfile generate-from-files ../../planfile --project-name "ci-pipeline" --focus quality --output ci-strategy.yaml

echo "--------------------------------------------------"
echo "[Pipeline Phase 2] Health Validation"
planfile health ci-strategy.yaml || echo "Health check had warnings/errors, but continuing for demo purposes..."

echo "--------------------------------------------------"
echo "[Pipeline Phase 3] Merge with Security Template"
# Generate a baseline security template
planfile template web security --output security-baseline.yaml

# Merge project strategy with security baseline
planfile merge ci-strategy.yaml security-baseline.yaml --name "Combined Project+Security Strategy" --output final-strategy.yaml

echo "--------------------------------------------------"
echo "[Pipeline Phase 4] Apply Strategy (Dry-Run)"
# Dry run to see what tickets/tasks would be created
planfile apply final-strategy.yaml . --dry-run

echo "✅ ADVANCED PIPELINE COMPLETED!"
