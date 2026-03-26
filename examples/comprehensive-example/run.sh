#!/bin/bash
set -e

echo "🌐 COMPREHENSIVE PLANFILE PIPELINE"
echo "A full lifecycle pipeline using bash and the planfile CLI."
echo "--------------------------------------------------"

echo "[Step 1] Generate Application Strategy from Files"
planfile generate-from-files ../../ --project-name "comprehensive-demo" --focus security --output comprehensive.yaml

echo "--------------------------------------------------"
echo "[Step 2] Display Extracted Statistics"
planfile stats comprehensive.yaml

echo "--------------------------------------------------"
echo "[Step 3] Run Structural Validation"
planfile validate comprehensive.yaml

echo "--------------------------------------------------"
echo "[Step 4] Human Review Output"
planfile review comprehensive.yaml

echo "--------------------------------------------------"
echo "[Step 5] Apply Configuration (Dry-Run)"
# Dry run simulates ticket creation / dispatch
planfile apply comprehensive.yaml . --dry-run

echo "--------------------------------------------------"
echo "✅ Comprehensive Pipeline Completed Successfully!"
