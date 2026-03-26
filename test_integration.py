#!/usr/bin/env python3
"""
Test the integrated planfile generation functionality.
"""

import sys
import os
sys.path.insert(0, '.')

from planfile.analysis.generator import generator
from planfile.loaders.yaml_loader import save_strategy_yaml


def test_integration():
    """Test the integrated generation functionality."""
    print("=" * 60)
    print("TESTING INTEGRATED PLANFILE GENERATION")
    print("=" * 60)
    
    # Test 1: Generate from current project
    print("\n1. Testing generate_from_current_project...")
    try:
        strategy = generator.generate_from_current_project(
            project_path=".",
            project_name="test-project",
            max_sprints=2,
            focus_area="quality"
        )
        
        print("✓ Generation successful!")
        print(f"  Type: {type(strategy)}")
        
        if isinstance(strategy, dict):
            print(f"  Name: {strategy.get('name', 'N/A')}")
            print(f"  Goals: {len(strategy.get('goals', []))}")
            print(f"  Sprints: {len(strategy.get('sprints', []))}")
            print(f"  Quality gates: {len(strategy.get('quality_gates', []))}")
        
        # Save to file
        save_strategy_yaml(strategy, "test-integrated.yaml")
        print("✓ Saved to test-integrated.yaml")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Test file analyzer directly
    print("\n2. Testing file analyzer...")
    try:
        from planfile.analysis.file_analyzer import FileAnalyzer
        
        analyzer = FileAnalyzer()
        result = analyzer.analyze_directory(
            Path("examples/strategies"),
            patterns=["*.yaml"]
        )
        
        print(f"✓ Analysis successful!")
        print(f"  Files analyzed: {len(result['analyzed_files'])}")
        print(f"  Issues found: {result['summary']['total_issues']}")
        print(f"  Metrics: {result['summary']['total_metrics']}")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    # Test 3: Test sprint generator
    print("\n3. Testing sprint generator...")
    try:
        from planfile.analysis.sprint_generator import SprintGenerator
        
        sprint_gen = SprintGenerator()
        
        # Mock analysis result
        mock_result = {
            'issues': [
                {
                    'title': 'Test issue',
                    'description': 'A test issue',
                    'priority': 'high',
                    'category': 'bug',
                    'file_path': 'test.py',
                    'line_number': 10,
                    'effort_estimate': '2h',
                    'tags': ['test']
                }
            ],
            'metrics': [],
            'tasks': []
        }
        
        sprints = sprint_gen.generate_sprints(mock_result, max_sprints=2)
        tickets = sprint_gen.generate_tickets(mock_result)
        
        print(f"✓ Sprint generation successful!")
        print(f"  Sprints: {len(sprints)}")
        print(f"  Tickets: {sum(len(v) for v in tickets.values())}")
        
    except Exception as e:
        print(f"✗ Failed: {e}")
    
    print("\n" + "=" * 60)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 60)
    
    print("\nUsage Examples:")
    print("1. CLI Command:")
    print("   python3 -m planfile.cli.commands generate-from-files .")
    print("\n2. Python API:")
    print("   from planfile.analysis.generator import generator")
    print("   strategy = generator.generate_from_current_project('.')")
    print("\n3. Custom Analysis:")
    print("   from planfile.analysis.file_analyzer import FileAnalyzer")
    print("   analyzer = FileAnalyzer()")
    print("   result = analyzer.analyze_directory(Path('.'))")


if __name__ == "__main__":
    from pathlib import Path
    test_integration()
