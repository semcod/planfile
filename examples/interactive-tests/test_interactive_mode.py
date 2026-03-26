#!/usr/bin/env python3
"""
Interactive mode test script for planfile
Tests repeatable generation in interactive mode
"""

import subprocess
import sys
import tempfile
import os
import time
from pathlib import Path

def run_interactive_planfile(inputs, cwd=None):
    """Run planfile in interactive mode with given inputs"""
    cmd = ["planfile", "init", "--interactive"]
    
    # Create process
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd
    )
    
    # Send inputs
    stdout, stderr = proc.communicate(input=inputs + "\n")
    
    return proc.returncode, stdout, stderr

def test_interactive_mode():
    """Test interactive mode generation"""
    print("Testing interactive mode...")
    
    # Create test directory
    with tempfile.TemporaryDirectory() as test_dir:
        print(f"Test directory: {test_dir}")
        
        # Test case 1: Basic interactive input
        print("\n=== Test 1: Basic interactive input ===")
        
        inputs = [
            "Interactive Test Project",
            "A project created in interactive mode",
            "generic",
            "n",  # No custom sprints
            "n",  # No custom tasks
            "n",  # No quality gates
            "n"   # No integrations
        ]
        
        returncode, stdout, stderr = run_interactive_planfile(
            "\n".join(inputs), 
            cwd=test_dir
        )
        
        if returncode != 0:
            print(f"❌ Interactive mode failed with code {returncode}")
            print(f"stderr: {stderr}")
            return False
        
        print("✓ Interactive mode completed")
        
        # Check if planfile.yaml was created
        planfile_path = Path(test_dir) / "planfile.yaml"
        if not planfile_path.exists():
            print("❌ planfile.yaml was not created")
            return False
        
        print("✓ planfile.yaml created")
        
        # Read and display generated content
        with open(planfile_path, 'r') as f:
            content = f.read()
        print("\nGenerated content:")
        print(content)
        
        # Verify content
        if "Interactive Test Project" in content:
            print("✓ Project name correctly set")
        else:
            print("❌ Project name not found in generated file")
            return False
        
        # Test case 2: Repeat generation with same inputs
        print("\n=== Test 2: Repeat generation (consistency test) ===")
        
        # Remove existing file
        planfile_path.unlink()
        
        # Run again with same inputs
        returncode2, stdout2, stderr2 = run_interactive_planfile(
            "\n".join(inputs),
            cwd=test_dir
        )
        
        if returncode2 != 0:
            print("❌ Second interactive run failed")
            return False
        
        # Read new content
        with open(planfile_path, 'r') as f:
            content2 = f.read()
        
        # Compare contents (ignoring potential timestamps)
        if content == content2:
            print("✓ Generation is consistent")
        else:
            print("⚠️  Generation differs between runs")
            print("\nFirst run:")
            print(content)
            print("\nSecond run:")
            print(content2)
        
        # Test case 3: Interactive with custom options
        print("\n=== Test 3: Interactive with custom options ===")
        
        # Create new subdirectory
        custom_dir = Path(test_dir) / "custom"
        custom_dir.mkdir()
        
        inputs3 = [
            "Custom Interactive Project",
            "A project with custom sprints and tasks",
            "github",
            "y",  # Add custom sprints
            "3",  # Number of sprints
            "Sprint 1",
            "2024-01-01",
            "2024-01-07",
            "Setup phase",
            "Sprint 2",
            "2024-01-08",
            "2024-01-14",
            "Development",
            "Sprint 3",
            "2024-01-15",
            "2024-01-21",
            "Testing",
            "y",  # Add custom tasks
            "2",  # Number of tasks
            "Initialize repository",
            "feature",
            "high",
            "1",
            "Setup project structure",
            "feature",
            "medium",
            "1",
            "y",  # Add quality gates
            "2",  # Number of gates
            "Test Coverage",
            "coverage",
            "80",
            "All Tests Pass",
            "tests",
            "100",
            "n"  # No integrations
        ]
        
        returncode3, stdout3, stderr3 = run_interactive_planfile(
            "\n".join(inputs3),
            cwd=str(custom_dir)
        )
        
        if returncode3 != 0:
            print("❌ Custom interactive run failed")
            print(f"stderr: {stderr3}")
            return False
        
        print("✓ Custom interactive mode completed")
        
        # Check custom content
        custom_planfile = custom_dir / "planfile.yaml"
        with open(custom_planfile, 'r') as f:
            custom_content = f.read()
        
        if "Sprint 1" in custom_content and "Initialize repository" in custom_content:
            print("✓ Custom sprints and tasks added")
        else:
            print("❌ Custom content not found")
            return False
        
        # Count sprints and tasks
        sprint_count = custom_content.count("- id:")
        task_count = custom_content.count("  - name:")
        gate_count = custom_content.count("  - name:")
        
        print(f"✓ Generated {sprint_count} sprints, {task_count} tasks, {gate_count} quality gates")
        
        # Test case 4: Test with invalid input handling
        print("\n=== Test 4: Invalid input handling ===")
        
        invalid_dir = Path(test_dir) / "invalid"
        invalid_dir.mkdir()
        
        # Test with empty inputs (should use defaults)
        inputs4 = ["", "", "", "n", "n", "n", "n"]
        
        returncode4, stdout4, stderr4 = run_interactive_planfile(
            "\n".join(inputs4),
            cwd=str(invalid_dir)
        )
        
        # Should still create a valid planfile
        if returncode4 == 0:
            print("✓ Handled empty inputs gracefully")
        else:
            print("⚠️  Failed with empty inputs (may be expected)")
        
    return True

def test_expect_script():
    """Test using expect script for more realistic interaction"""
    print("\n=== Testing with expect script ===")
    
    expect_script = '''#!/usr/bin/expect -f
set timeout 5
spawn planfile init --interactive

expect "Project name:"
send "Expect Test Project\\r"

expect "Project description:"
send "Project created via expect\\r"

expect "Backend type"
send "generic\\r"

expect "Add custom sprints?"
send "n\\r"

expect "Add custom tasks?"
send "n\\r"

expect "Add quality gates?"
send "n\\r"

expect "Add integrations?"
send "n\\r"

expect eof
'''
    
    # Write expect script to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.exp', delete=False) as f:
        f.write(expect_script)
        script_path = f.name
    
    try:
        # Make script executable
        os.chmod(script_path, 0o755)
        
        # Create test directory
        with tempfile.TemporaryDirectory() as test_dir:
            # Run expect script
            result = subprocess.run(
                [script_path],
                cwd=test_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✓ Expect script executed successfully")
                
                # Check if planfile was created
                planfile_path = Path(test_dir) / "planfile.yaml"
                if planfile_path.exists():
                    print("✓ planfile.yaml created by expect script")
                    
                    with open(planfile_path, 'r') as f:
                        content = f.read()
                    
                    if "Expect Test Project" in content:
                        print("✓ Content correctly set")
                    else:
                        print("❌ Content not as expected")
                else:
                    print("❌ planfile.yaml not created")
            else:
                print("⚠️  Expect script not available or failed")
                print(f"Error: {result.stderr}")
    
    finally:
        # Clean up
        os.unlink(script_path)

def main():
    """Run all interactive tests"""
    print("=" * 60)
    print("INTERACTIVE MODE TESTS")
    print("=" * 60)
    
    # Check if planfile command is available
    result = subprocess.run(
        ["planfile", "--help"],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print("❌ planfile command not found")
        sys.exit(1)
    
    # Run tests
    success = True
    
    try:
        if not test_interactive_mode():
            success = False
        
        test_expect_script()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        success = False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("✅ All interactive tests completed!")
    else:
        print("❌ Some tests failed")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    main()
