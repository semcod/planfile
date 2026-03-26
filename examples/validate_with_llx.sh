#!/bin/bash
# Validate planfile examples using LLX

echo "Planfile Example Validation with LLX"
echo "====================================="

# Check if LLX is available
if ! command -v llx &> /dev/null; then
    echo "⚠️  LLX not found. Install with: pip install llx"
    echo "   Falling back to basic validation"
    LLX_AVAILABLE=false
else
    echo "✅ LLX found"
    LLX_AVAILABLE=true
fi

# Function to validate a file
validate_file() {
    local file=$1
    echo -e "\nValidating: $file"
    
    if [ "$LLX_AVAILABLE" = true ]; then
        # Use LLX for validation
        case "${file##*.}" in
            yaml|yml)
                echo "  YAML structure validation..."
                python3 -c "import yaml; yaml.safe_load(open('$file'))" && echo "  ✅ Valid YAML" || echo "  ❌ Invalid YAML"
                ;;
            py)
                echo "  Python syntax validation..."
                python3 -m py_compile "$file" && echo "  ✅ Valid Python" || echo "  ❌ Invalid Python"
                
                if [ "$LLX_AVAILABLE" = true ]; then
                    echo "  Code complexity analysis..."
                    llx analyze "$file" 2>/dev/null || echo "  ⚠️  Could not analyze with LLX"
                fi
                ;;
            json)
                echo "  JSON structure validation..."
                python3 -c "import json; json.load(open('$file'))" && echo "  ✅ Valid JSON" || echo "  ❌ Invalid JSON"
                ;;
        esac
    else
        # Basic validation
        case "${file##*.}" in
            yaml|yml)
                python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null && echo "  ✅ Valid YAML" || echo "  ❌ Invalid YAML"
                ;;
            py)
                python3 -m py_compile "$file" 2>/dev/null && echo "  ✅ Valid Python" || echo "  ❌ Invalid Python"
                ;;
            json)
                python3 -c "import json; json.load(open('$file'))" 2>/dev/null && echo "  ✅ Valid JSON" || echo "  ❌ Invalid JSON"
                ;;
        esac
    fi
}

# Find and validate all generated files
echo "\nScanning for generated files..."
find . -type f \( -name "*.yaml" -o -name "*.yml" -o -name "*.py" -o -name "*.json" \) -not -path "./venv/*" -not -path "./.venv/*" | while read file; do
    validate_file "$file"
done

echo "\nValidation complete!"
