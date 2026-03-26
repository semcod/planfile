#!/usr/bin/env python3
"""
Test script to validate all example strategies work correctly.
"""

import os
import sys
import subprocess
from pathlib import Path
import yaml

def validate_strategy_yaml(file_path):
    """Validate a strategy YAML file."""
    print(f"\n🔍 Validating: {file_path.name}")
    
    try:
        with open(file_path, 'r') as f:
            strategy = yaml.safe_load(f)
        
        # Check required fields
        required_fields = ['name', 'project_name', 'project_type', 'domain', 'goal']
        missing = [field for field in required_fields if field not in strategy]
        if missing:
            print(f"  ❌ Missing required fields: {', '.join(missing)}")
            return False
        
        # Check sprints
        if 'sprints' in strategy:
            for sprint in strategy['sprints']:
                if 'id' not in sprint or 'name' not in sprint:
                    print(f"  ❌ Sprint missing id or name")
                    return False
        
        # Check quality gates
        if 'quality_gates' in strategy:
            for gate in strategy['quality_gates']:
                if 'metric' not in gate or 'threshold' not in gate:
                    print(f"  ❌ Quality gate missing metric or threshold")
                    return False
        
        print(f"  ✅ Valid strategy structure")
        return True
        
    except yaml.YAMLError as e:
        print(f"  ❌ YAML error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_strategy_generation(strategy_path):
    """Test strategy generation with the YAML file."""
    print(f"\n🚀 Testing generation with: {strategy_path.name}")
    
    cmd = [
        sys.executable, '-m', 'planfile.cli.commands',
        'generate',
        '--dry-run',
        str(strategy_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  ✅ Generation successful")
            return True
        else:
            print(f"  ❌ Generation failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ⏰ Generation timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def test_strategy_validation(strategy_path):
    """Test strategy validation."""
    print(f"\n✅ Testing validation for: {strategy_path.name}")
    
    cmd = [
        sys.executable, '-m', 'planfile.cli.commands',
        'validate',
        str(strategy_path)
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"  ✅ Validation passed")
            return True
        else:
            print(f"  ❌ Validation failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ⏰ Validation timed out")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Planfile Example Strategies")
    print("=" * 60)
    
    strategies_dir = Path("./strategies")
    if not strategies_dir.exists():
        print(f"❌ Strategies directory not found: {strategies_dir}")
        sys.exit(1)
    
    # Find all YAML files
    yaml_files = list(strategies_dir.glob("*.yaml")) + list(strategies_dir.glob("*.yml"))
    
    if not yaml_files:
        print("❌ No YAML strategy files found")
        sys.exit(1)
    
    print(f"\nFound {len(yaml_files)} strategy files")
    
    # Test each strategy
    results = []
    for strategy_file in sorted(yaml_files):
        print("\n" + "=" * 40)
        
        # Validate YAML structure
        valid = validate_strategy_yaml(strategy_file)
        
        if valid:
            # Test validation command
            validation_ok = test_strategy_validation(strategy_file)
            
            # Test generation (dry run)
            generation_ok = test_strategy_generation(strategy_file)
            
            results.append({
                'file': strategy_file.name,
                'valid': valid,
                'validation': validation_ok,
                'generation': generation_ok
            })
        else:
            results.append({
                'file': strategy_file.name,
                'valid': False,
                'validation': False,
                'generation': False
            })
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total = len(results)
    passed = sum(1 for r in results if all([r['valid'], r['validation'], r['generation']]))
    
    print(f"\nTotal strategies: {total}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {total - passed}")
    
    if total - passed > 0:
        print("\nFailed strategies:")
        for r in results:
            if not all([r['valid'], r['validation'], r['generation']]):
                status = []
                if not r['valid']: status.append("invalid")
                if not r['validation']: status.append("validation failed")
                if not r['generation']: status.append("generation failed")
                print(f"  - {r['file']}: {', '.join(status)}")
    
    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()
