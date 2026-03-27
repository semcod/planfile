#!/bin/bash

# Code2LLM Integration Example
# Demonstrates full pipeline: init → create tickets → import from evolution.toon

set -e

echo "🚀 Code2LLM Integration Example"
echo "=============================="
echo "This example shows how to import tasks from code analysis into planfile"
echo ""

# Clean up any existing planfile
echo "🧹 Cleaning up previous example..."
rm -rf .planfile planfile.yaml

# Create minimal planfile.yaml
echo "📝 Creating planfile.yaml..."
cat > planfile.yaml << EOF
name: "Code2LLM Strategy"
description: "Strategy for code2llm integration example"

project:
  name: "Code2LLM Demo"
  description: "Example project showing code2llm integration"
  prefix: "C2L"

sprint:
  id: "sprint-001"
  name: "Code Analysis Sprint"
  status: "active"
  start_date: "2026-03-27"
  end_date: "2026-04-10"
  tickets: {}

backlog:
  tickets: {}
EOF

# Full pipeline test
echo "📝 Full Pipeline Test:"
echo "--------------------"

echo "1️⃣ Creating test ticket..."
planfile ticket create "Test ticket" --priority normal --description "Manual test ticket"

echo ""
echo "2️⃣ Listing tickets (default format):"
planfile ticket list

echo ""
echo "3️⃣ Listing tickets (JSON format):"
planfile ticket list --format json

echo ""
echo "4️⃣ Importing ticket from stdin:"
echo '{"title":"From stdin","description":"Imported via stdin","priority":"high"}' | planfile ticket import --source test

echo ""
echo "5️⃣ Showing project statistics:"
planfile stats planfile.yaml

echo ""
echo "🔄 Import from Code2LLM:"
echo "----------------------"

echo "6️⃣ Importing tasks from evolution.toon to backlog:"
planfile ticket import --from evolution.toon --source code2llm --sprint backlog

echo ""
echo "7️⃣ Updated ticket list:"
planfile ticket list

echo ""
echo "📊 Running Code Analysis:"
echo "-----------------------"

echo "8️⃣ Running code2llm analysis (if installed):"
if command -v code2llm &> /dev/null; then
    code2llm . -f toon,evolution
    echo "✅ Analysis complete. Check evolution.toon for updated tasks."
else
    echo "⚠️  code2llm not installed. Install with:"
    echo "   pip install code2llm"
    echo ""
    echo "Or run:"
    echo "   npm install -g code2llm"
fi

echo ""
echo "🎯 Target Metrics:"
echo "-----------------"
echo "• CC̄ ≤ 3.0 (average cyclomatic complexity)"
echo "• vallm validation ≥ 95%"
echo "• 0 god modules (high complexity modules)"

echo ""
echo "📋 Next Steps:"
echo "-------------"
echo "1. Review imported tickets"
echo "2. Prioritize tasks for current sprint"
echo "3. Move tickets from backlog to sprint:"
echo "   planfile ticket move C2L-001 --to current"
echo ""
echo "4. Update ticket status:"
echo "   planfile ticket update C2L-001 --status in-progress"
echo ""
echo "5. Generate metrics report:"
echo "   planfile stats"
