#!/bin/bash

# Redup Integration Example
# Demonstrates full pipeline: init → create tickets → import from duplication.toon.yaml

set -e

echo "🚀 Redup Integration Example"
echo "==========================="
echo "This example shows how to import code duplication issues from redup into planfile"
echo ""

# Clean up any existing planfile
echo "🧹 Cleaning up previous example..."
rm -rf .planfile planfile.yaml

# Create minimal planfile.yaml
echo "📝 Creating planfile.yaml..."
cat > planfile.yaml << EOF
name: "Redup Strategy"
description: "Strategy for redup integration example"

project:
  name: "Redup Demo"
  description: "Example project showing redup integration"
  prefix: "RD"

sprint:
  id: "sprint-001"
  name: "Code Quality Sprint"
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
echo "🔄 Import from Redup:"
echo "-------------------"

echo "6️⃣ Importing duplication issues to backlog:"
planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog

echo ""
echo "7️⃣ Updated ticket list:"
planfile ticket list

echo ""
echo "📊 Running Duplication Analysis:"
echo "--------------------------------"

echo "8️⃣ Running redup analysis (if installed):"
if command -v redup &> /dev/null; then
    redup . --format toon
    echo "✅ Analysis complete. Check duplication.toon.yaml for updated results."
else
    echo "⚠️  redup not installed. Install with:"
    echo "   pip install redup"
    echo ""
    echo "Or from source:"
    echo "   cd /home/tom/github/semcod/redup && pip install -e ."
fi

echo ""
echo "🎯 Target Metrics:"
echo "-----------------"
echo "• 0 duplicate groups"
echo "• 100% unique code"
echo "• No repeated patterns > 3 lines"

echo ""
echo "📈 Duplication Impact:"
echo "---------------------"
echo "The imported tickets represent code duplication that should be refactored:"
echo ""
echo "High Impact (saves > 10 lines):"
echo "• Extract common base classes"
echo "• Create shared utility functions"
echo "• Consolidate similar implementations"
echo ""
echo "Medium Impact (saves 5-10 lines):"
echo "• Extract helper functions"
echo "• Create reusable components"
echo "• Merge similar code blocks"
echo ""
echo "Low Impact (saves < 5 lines):"
echo "• Inline small duplications"
echo "• Use macros or templates"
echo "• Consolidate trivial repetitions"

echo ""
echo "📋 Next Steps:"
echo "-------------"
echo "1. Review imported duplication tickets"
echo "2. Prioritize high-impact refactoring"
echo "3. Track progress with:"
echo "   planfile ticket list --status done"
echo ""
echo "4. Re-run duplication analysis after fixes:"
echo "   redup . --format toon"
echo ""
echo "5. Import updated results:"
echo "   planfile ticket import --from duplication.toon.yaml --source redup --sprint backlog"
