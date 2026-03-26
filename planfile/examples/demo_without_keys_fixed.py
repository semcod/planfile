#!/usr/bin/env python3
"""
Simple demonstration of planfile + LiteLLM integration.
This works without API keys by using mock responses.
"""

import os
import sys
import asyncio
from pathlib import Path
import yaml
import json

# Add planfile to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from planfile.llm.client import call_llm
from planfile.llm.generator import generate_strategy
from planfile.models import Strategy


def mock_llm_response(prompt: str, model: str = "mock") -> str:
    """Mock LLM response for demonstration."""
    return """
```yaml
name: AI-Powered Analytics Dashboard
project_name: AnalyticsAI
project_type: data-analytics
domain: business-intelligence
goal: Build real-time analytics dashboard with AI insights

sprints:
- id: sprint-1
  name: Foundation & Data Pipeline
  duration: 2 weeks
  objectives:
  - Set up data ingestion pipeline
  - Implement basic dashboard UI
  - Connect to data sources
  
  task_patterns:
  - name: Create data models
    description: Design and implement data models
    task_type: development
    priority: high
    estimate: 3d
    model_hints:
      planning: balanced
      implementation: balanced

- id: sprint-2
  name: AI Integration
  duration: 3 weeks
  objectives:
  - Implement ML models
  - Add predictive analytics
  - Create AI insights
  
  task_patterns:
  - name: Integrate ML models
    description: Add machine learning capabilities
    task_type: feature
    priority: high
    estimate: 5d
    model_hints:
      planning: premium
      implementation: premium

- id: sprint-3
  name: Polish & Deployment
  duration: 2 weeks
  objectives:
  - Performance optimization
  - Security hardening
  - Production deployment
  
  task_patterns:
  - name: Deploy to production
    description: Set up CI/CD and deploy
    task_type: deployment
    priority: critical
    estimate: 2d
    model_hints:
      planning: balanced
      implementation: balanced

quality_gates:
- metric: Performance
  threshold: Page load < 2 seconds
- metric: Accuracy
  threshold: AI predictions > 95% accuracy
- metric: Coverage
  threshold: Test coverage >= 80%
- metric: Security
  threshold: Zero critical vulnerabilities

tasks:
  critical_refactors:
  - name: Optimize data queries
    description: Improve query performance
    estimated_hours: 40
    complexity: high
    
  standard_refactors:
  - name: Refactor UI components
    description: Improve component reusability
    estimated_hours: 24
    complexity: medium
    
  test_writing:
  - name: Unit tests
    description: Comprehensive unit test suite
    estimated_hours: 60
    complexity: medium
    
  documentation:
  - name: API documentation
    description: Document all endpoints
    estimated_hours: 20
    complexity: low

metrics:
  target:
    data_sources: 10
    ml_models: 5
    dashboard_widgets: 20
    api_endpoints: 50
  quality:
    performance_score: 95
    accuracy_score: 95
    test_coverage: 80
    security_score: 100
```


def demonstrate_without_api_keys():
    """Demonstrate planfile functionality without API keys."""
    print("=" * 60)
    print("PLANFILE DEMONSTRATION (No API Keys Required)")
    print("=" * 60)
    
    # Create a mock strategy
    print("\n📝 1. Creating mock strategy...")
    
    mock_response = mock_llm_response("")
    
    # Extract YAML
    yaml_content = mock_response.split("```yaml")[1].split("```")[0]
    
    # Save strategy
    strategy_file = Path("mock-strategy.yaml")
    with open(strategy_file, 'w') as f:
        f.write(yaml_content)
    
    print(f"✅ Strategy saved to: {strategy_file}")
    
    # Validate with planfile
    print("\n✅ 2. Validating strategy with planfile...")
    cmd = [sys.executable, "-m", "planfile.cli.commands", "validate", str(strategy_file)]
    
    result = os.system(f"cd {Path.cwd()} && {' '.join(cmd)}")
    
    if result == 0:
        print("✅ Strategy is valid!")
    else:
        print("❌ Strategy validation failed")
    
    # Apply strategy (dry run)
    print("\n🎯 3. Applying strategy (dry run)...")
    cmd = [
        sys.executable, "-m", "planfile.cli.commands", "apply",
        str(strategy_file), ".", "--backend", "generic", "--dry-run"
    ]
    
    result = os.system(f"cd {Path.cwd()} && {' '.join(cmd)}")
    
    if result == 0:
        print("✅ Strategy applied successfully (dry run)!")
    else:
        print("❌ Strategy application failed")
    
    # Review strategy
    print("\n📊 4. Reviewing strategy...")
    cmd = [
        sys.executable, "-m", "planfile.cli.commands", "review",
        str(strategy_file), ".", "--backend", "generic"
    ]
    
    result = os.system(f"cd {Path.cwd()} && {' '.join(cmd)}")
    
    if result == 0:
        print("✅ Strategy review completed!")
    else:
        print("❌ Strategy review failed")
    
    # Show strategy structure
    print("\n📋 5. Strategy Structure:")
    with open(strategy_file, 'r') as f:
        strategy_data = yaml.safe_load(f)
    
    print(f"  - Name: {strategy_data.get('name')}")
    print(f"  - Project: {strategy_data.get('project_name')}")
    print(f"  - Type: {strategy_data.get('project_type')}")
    print(f"  - Sprints: {len(strategy_data.get('sprints', []))}")
    print(f"  - Quality Gates: {len(strategy_data.get('quality_gates', []))}")
    print(f"  - Task Categories: {list(strategy_data.get('tasks', {}).keys())}")
    
    # Clean up
    strategy_file.unlink()
    print(f"\n🧹 Cleaned up {strategy_file}")


def show_integration_examples():
    """Show examples of how to integrate with different LLM providers."""
    print("\n" + "=" * 60)
    print("LLM INTEGRATION EXAMPLES")
    print("=" * 60)
    
    examples = {
        "OpenAI": """
# Using OpenAI with LiteLLM
from planfile.llm.client import call_llm

response = call_llm(
    "Generate a strategy for e-commerce platform",
    model="gpt-4-turbo-preview",
    temperature=0.3
)
        """,
        
        "Anthropic via OpenRouter": """
# Using Anthropic through OpenRouter
import os
os.environ['OPENROUTER_API_KEY'] = 'your-key'

from planfile.llm.client import call_llm

response = call_llm(
    "Generate a microservices migration strategy",
    model="anthropic/claude-3-sonnet",
    temperature=0.3
)
        """,
        
        "Local Ollama": """
# Using local Ollama
from planfile.llm.adapters import LocalLLMAdapter

adapter = LocalLLMAdapter({
    'base_url': 'http://localhost:11434',
    'provider': 'ollama'
})

result = await adapter.test_strategy_generation(prompt, 'llama2')
        """,
        
        "Direct LiteLLM": """
# Using LiteLLM directly
import litellm

response = await litellm.acompletion(
    model="gpt-3.5-turbo",
    messages=[{
        "role": "user",
        "content": "Generate a YAML strategy..."
    }],
    temperature=0.3
)
        """
    }
    
    for provider, code in examples.items():
        print(f"\n🔌 {provider}:")
        print("-" * 40)
        print(code.strip())


def show_testing_approach():
    """Show how to test different LLM providers."""
    print("\n" + "=" * 60)
    print("TESTING APPROACH")
    print("=" * 60)
    
    print("""
1. Set up API keys:
   export OPENAI_API_KEY=your_key
   export OPENROUTER_API_KEY=your_key
   export GOOGLE_API_KEY=your_key

2. Test with built-in script:
   python3 planfile/examples/test_llm_adapters.py

3. Test specific integration:
   python3 planfile/examples/test_litellm_integration.py

4. Run full demo:
   python3 planfile/examples/llm_integration_demo.py

5. Compare results:
   - Check llm-test-results.json
   - Review generated strategies
   - Compare response times and costs
    """")


def main():
    """Main demonstration."""
    # Demonstrate without API keys
    demonstrate_without_api_keys()
    
    # Show integration examples
    show_integration_examples()
    
    # Show testing approach
    show_testing_approach()
    
    print("\n" + "=" * 60)
    print("✅ DEMONSTRATION COMPLETE")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Set up API keys for real LLM testing")
    print("2. Run the adapter test scripts")
    print("3. Compare different model performances")
    print("4. Choose the best model for your use case")


if __name__ == "__main__":
    main()
