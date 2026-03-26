#!/bin/bash
set -e

echo "🤖 PLANFILE LLM INTEGRATION DEMO"
echo "Demonstrating how planfile generates LLM prompts for smart strategy creation."

echo "--------------------------------------------------"
echo "Generating Strategy with LLM explicitly (Dry Run)"
# A dry-run will generate the prompt and output it, but won't send it to the LLM.
# This avoids needing API keys just to test the integration.
planfile generate ../../planfile --output llm-strategy.yaml --sprints 2 --dry-run || true

echo "✅ Complete! (Notice the generated prompt in output above)"
