#!/bin/bash
# Advanced Usage Example Runner

echo "🎯" * 20
echo "ADVANCED USAGE EXAMPLES"
echo "🎯" * 20
echo ""

# Check if planfile is installed
if ! python3 -c "import planfile" 2>/dev/null; then
    echo "❌ planfile not found. Install with:"
    echo "   pip install -e ."
    exit 1
fi

echo "Advanced patterns demonstrated:"
echo "  ✓ Custom file patterns"
echo "  ✓ Focus-specific strategies"
echo "  ✓ Iterative refinement"
echo "  ✓ Batch processing"
echo "  ✓ Custom metrics"
echo "  ✓ CI/CD automation"
echo ""

# Run the example
python3 advanced_usage_examples.py

echo ""
echo "✅ Advanced usage examples complete!"
echo ""
echo "Generated files:"
echo "  Custom patterns:"
ls -la custom-patterns-*.yaml 2>/dev/null | grep -v "^total" || echo "    None"
echo ""
echo "  Focus strategies:"
ls -la focus-*-strategy.yaml 2>/dev/null | grep -v "^total" || echo "    None"
echo ""
echo "  Iterative versions:"
ls -la iterative-*.yaml 2>/dev/null | grep -v "^total" || echo "    None"
echo ""
echo "  Batch results:"
ls -la batch-*-strategy.yaml 2>/dev/null | grep -v "^total" || echo "    None"
echo ""
echo "  CI/CD artifacts:"
ls -la ci-*.* 2>/dev/null | grep -v "^total" || echo "    None"
echo ""
echo "🎉 All examples completed!"
echo ""
echo "Tips:"
echo "  - Combine patterns for custom workflows"
echo "  - Check generated YAML files for structure"
echo "  - Use ci-workflow.sh in your pipelines"
echo "  - Modify examples for your needs"
