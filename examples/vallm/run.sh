#!/bin/bash

# Vallm Integration Example
# Demonstrates full pipeline: init → create tickets → import from validation.toon

set -e

echo "🚀 Vallm Integration Example"
echo "============================"
echo "This example shows how to import validation errors from vallm into planfile"
echo ""

# Clean up any existing planfile
echo "🧹 Cleaning up previous example..."
rm -rf .planfile planfile.yaml

# Create minimal planfile.yaml
echo "📝 Creating planfile.yaml..."
cat > planfile.yaml << EOF
name: "Vallm Strategy"
description: "Strategy for vallm integration example"

project:
  name: "Vallm Demo"
  description: "Example project showing vallm integration"
  prefix: "VL"

strategy:
  goals:
    - "Fix validation errors"
    - "Improve code quality"
    - "Maintain coding standards"
  
  quality_gates:
    - "CC̄ ≤ 3.0"
    - "vallm validation ≥ 95%"
    - "0 god modules"
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
echo "🔄 Import from Vallm:"
echo "-------------------"

echo "6️⃣ Importing validation errors to current sprint:"
planfile ticket import --from validation.toon --source vallm --sprint current

echo ""
echo "7️⃣ Updated ticket list:"
planfile ticket list

echo ""
echo "📊 Running Validation:"
echo "---------------------"

echo "8️⃣ Running vallm validation (if installed):"
if command -v vallm &> /dev/null; then
    vallm batch . --recursive
    echo "✅ Validation complete. Check validation.toon for updated errors."
else
    echo "⚠️  vallm not installed. Install with:"
    echo "   pip install vallm"
    echo ""
    echo "Or run:"
    echo "   npm install -g vallm"
fi

echo ""
echo "🎯 Target Metrics:"
echo "-----------------"
echo "• CC̄ ≤ 3.0 (average cyclomatic complexity)"
echo "• vallm validation ≥ 95%"
echo "• 0 god modules (high complexity modules)"

echo ""
echo "📈 Quality Gates:"
echo "---------------"
echo "The imported tickets represent quality issues that should be addressed:"
echo ""
echo "Critical Issues (Priority: critical):"
echo "• Module not found errors"
echo "• Undefined variable errors"
echo "• Security vulnerabilities"
echo ""
echo "High Priority Issues:"
echo "• Code complexity violations"
echo "• Import errors"
echo "• Performance issues"
echo ""
echo "Medium Priority Issues:"
echo "• Style violations"
echo "• Missing documentation"
echo "• Unused imports"

echo ""
echo "📋 Next Steps:"
echo "-------------"
echo "1. Review imported validation tickets"
echo "2. Fix critical issues first"
echo "3. Track progress with:"
echo "   planfile ticket list --status done"
echo ""
echo "4. Re-run validation after fixes:"
echo "   vallm batch . --recursive"
echo ""
echo "5. Import updated validation results:"
echo "   planfile ticket import --from validation.toon --source vallm --sprint current"
