"""
LLX integration for validating planfile examples
"""

import os
import subprocess
from pathlib import Path
from typing import Any


class LLXValidator:
    """Use LLX to validate generated code and strategies."""

    def __init__(self, llx_path: str | None = None):
        self.llx_path = llx_path or "llx"

    async def validate_strategy(self, strategy_path: Path) -> dict[str, Any]:
        """Validate a strategy file using LLX."""
        if not self._is_llx_available():
            return {"error": "LLX not available"}

        # Use LLX to analyze the strategy
        try:
            # Check strategy structure
            result = subprocess.run(
                [self.llx_path, "validate", str(strategy_path)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return {"valid": True, "output": result.stdout}
            else:
                return {"valid": False, "errors": result.stderr}
        except Exception as e:
            return {"error": str(e)}

    async def analyze_generated_code(self, code_path: Path) -> dict[str, Any]:
        """Analyze generated code using LLX."""
        if not self._is_llx_available():
            return self._basic_code_analysis(code_path)

        try:
            # Use LLX code analysis tools
            result = subprocess.run(
                [self.llx_path, "analyze", str(code_path)],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return self._parse_llx_analysis(result.stdout)
            else:
                return self._basic_code_analysis(code_path)
        except Exception:
            return self._basic_code_analysis(code_path)

    def _is_llx_available(self) -> bool:
        """Check if LLX is available."""
        try:
            subprocess.run([self.llx_path, "--version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _parse_llx_analysis(self, output: str) -> dict[str, Any]:
        """Parse LLX analysis output."""
        # Parse LLX output format
        lines = output.strip().split('\n')
        metrics = {}

        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                metrics[key.strip()] = value.strip()

        return {
            "tool": "llx",
            "metrics": metrics,
            "valid": True
        }

    def _basic_code_analysis(self, code_path: Path) -> dict[str, Any]:
        """Basic code analysis without LLX."""
        try:
            content = code_path.read_text(encoding='utf-8')

            analysis = {
                "tool": "basic",
                "lines": len(content.splitlines()),
                "characters": len(content),
                "file_type": code_path.suffix
            }

            if code_path.suffix == '.py':
                # Basic Python metrics
                analysis.update({
                    "imports": content.count('import ') + content.count('from '),
                    "functions": content.count('def '),
                    "classes": content.count('class '),
                    "comments": content.count('#')
                })

            return analysis
        except Exception as e:
            return {"error": str(e)}

# Create a simple validation script using LLX
def create_validation_script():
    """Create a validation script that uses LLX."""
    script = '''#!/bin/bash
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
    echo -e "\\nValidating: $file"
    
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
echo "\\nScanning for generated files..."
find . -type f \\( -name "*.yaml" -o -name "*.yml" -o -name "*.py" -o -name "*.json" \\) -not -path "./venv/*" -not -path "./.venv/*" | while read file; do
    validate_file "$file"
done

echo "\\nValidation complete!"
'''

    with open("./validate_with_llx.sh", "w") as f:
        f.write(script)

    os.chmod("./validate_with_llx.sh", 0o755)
    print("✅ Created validation script: ./validate_with_llx.sh")

if __name__ == "__main__":
    create_validation_script()
