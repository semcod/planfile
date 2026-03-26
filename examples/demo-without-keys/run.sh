#!/bin/bash
set -e

echo "🚫 PLANFILE DEMO WITHOUT API KEYS"
echo "Demonstrating how planfile can perform rich static analysis entirely locally."

echo "--------------------------------------------------"
echo "Generating Strategy from Local codebase without LLM"
# The 'generate-from-files' command relies on purely static code analysis techniques
# allowing usage without OpenAI / LiteLLM keys.
planfile generate-from-files ../../planfile --project-name "demo-no-llm" --output local-strategy.yaml

echo "--------------------------------------------------"
echo "Stats of Local Strategy"
planfile stats local-strategy.yaml

echo "✅ Complete!"
