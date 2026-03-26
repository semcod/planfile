#!/usr/bin/env python3
"""
Test planfile strategies with various LLM providers using adapters.
"""

import asyncio
import os
import sys
from pathlib import Path
import json
from datetime import datetime

# Add planfile to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile.llm.adapters import (
    LLMTestRunner,
    LiteLLMAdapter,
    OpenRouterAdapter,
    LocalLLMAdapter,
    LLMTestResult
)


async def main():
    """Run LLM adapter tests."""
    print("=" * 60)
    print("PLANFILE LLM ADAPTER TESTS")
    print("=" * 60)
    
    # Initialize test runner
    runner = LLMTestRunner()
    
    # Configure adapters
    adapters_config = {
        'litellm': {
            'default_model': 'gpt-3.5-turbo',
            'api_key': os.environ.get('OPENAI_API_KEY')
        },
        'openrouter': {
            'default_model': 'anthropic/claude-3-haiku',
            'api_key': os.environ.get('OPENROUTER_API_KEY')
        },
        'local-ollama': {
            'default_model': 'llama2',
            'base_url': 'http://localhost:11434',
            'provider': 'ollama'
        },
        'local-lmstudio': {
            'default_model': 'local-model',
            'base_url': 'http://localhost:1234/v1',
            'provider': 'openai-compatible'
        }
    }
    
    # Register adapters
    for name, config in adapters_config.items():
        try:
            if name == 'litellm':
                if config['api_key']:
                    adapter = LiteLLMAdapter(config)
                    runner.register_adapter(name, adapter)
                    print(f"✅ Registered {name} adapter")
                else:
                    print(f"⚠️  Skipping {name} (no API key)")
            elif name == 'openrouter':
                if config['api_key']:
                    adapter = OpenRouterAdapter(config)
                    runner.register_adapter(name, adapter)
                    print(f"✅ Registered {name} adapter")
                else:
                    print(f"⚠️  Skipping {name} (no API key)")
            elif name.startswith('local'):
                adapter = LocalLLMAdapter(config)
                runner.register_adapter(name, adapter)
                print(f"✅ Registered {name} adapter")
        except Exception as e:
            print(f"❌ Failed to register {name}: {e}")
    
    if not runner.adapters:
        print("\n❌ No adapters registered. Please configure API keys or start local servers.")
        print("\nTo set up:")
        print("  export OPENAI_API_KEY=your_key")
        print("  export OPENROUTER_API_KEY=your_key")
        print("  # Or start Ollama: ollama serve")
        print("  # Or start LM Studio with local server")
        return
    
    # Select strategy to test
    strategies_dir = Path(__file__).parent / "strategies"
    test_strategies = [
        "microservices-migration.yaml",
        "ml-pipeline-optimization.yaml",
        "security-hardening.yaml"
    ]
    
    print(f"\n📁 Testing strategies from: {strategies_dir}")
    
    # Models to test per adapter
    test_models = {
        'litellm': ['gpt-3.5-turbo'],
        'openrouter': ['anthropic/claude-3-haiku', 'meta-llama/llama-3-8b-instruct'],
        'local-ollama': ['llama2'],
        'local-lmstudio': [None]
    }
    
    # Run tests
    all_results = {}
    
    for strategy_file in test_strategies:
        strategy_path = strategies_dir / strategy_file
        
        if not strategy_path.exists():
            print(f"⚠️  Strategy not found: {strategy_file}")
            continue
        
        print(f"\n🚀 Testing strategy: {strategy_file}")
        print("-" * 60)
        
        try:
            results = await runner.test_strategy_with_all_adapters(
                strategy_path,
                test_models
            )
            all_results[strategy_file] = results
            
            # Show quick summary
            for adapter_name, adapter_results in results.items():
                successful = sum(1 for r in adapter_results if r.success)
                total = len(adapter_results)
                avg_time = sum(r.response_time for r in adapter_results) / total
                print(f"  {adapter_name}: {successful}/{total} successful, avg {avg_time:.2f}s")
                
        except Exception as e:
            print(f"❌ Error testing {strategy_file}: {e}")
    
    # Generate report
    if all_results:
        print("\n" + "=" * 60)
        print("GENERATING REPORT")
        print("=" * 60)
        
        report = runner.generate_report(all_results)
        
        # Save report
        report_file = Path("llm-test-report.md")
        with open(report_file, 'w') as f:
            f.write(report)
        
        print(f"✅ Report saved to: {report_file}")
        
        # Save raw results
        results_file = Path("llm-test-results.json")
        with open(results_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'results': {
                    strategy: {
                        adapter: [
                            {
                                'provider': r.provider,
                                'model': r.model,
                                'success': r.success,
                                'response_time': r.response_time,
                                'token_count': r.token_count,
                                'cost': r.cost,
                                'error': r.error,
                                'response': r.response[:500] if r.response else None
                            }
                            for r in adapter_results
                        ]
                        for adapter, adapter_results in results.items()
                    }
                    for strategy, results in all_results.items()
                }
            }, f, indent=2)
        
        print(f"✅ Raw results saved to: {results_file}")
        
        # Show best performers
        print("\n🏆 BEST PERFORMERS")
        print("-" * 60)
        
        all_test_results = []
        for strategy_results in all_results.values():
            for adapter_results in strategy_results.values():
                all_test_results.extend(adapter_results)
        
        successful = [r for r in all_test_results if r.success]
        
        if successful:
            # Fastest
            fastest = min(successful, key=lambda x: x.response_time)
            print(f"⚡ Fastest: {fastest.provider} {fastest.model} ({fastest.response_time:.2f}s)")
            
            # Cheapest (if cost data available)
            with_cost = [r for r in successful if r.cost is not None]
            if with_cost:
                cheapest = min(with_cost, key=lambda x: x.cost)
                print(f"💰 Cheapest: {cheapest.provider} {cheapest.model} (${cheapest.cost:.4f})")
            
            # Most tokens (if available)
            with_tokens = [r for r in successful if r.token_count is not None]
            if with_tokens:
                most_tokens = max(with_tokens, key=lambda x: x.token_count)
                print(f"📝 Most detailed: {most_tokens.provider} {most_tokens.model} ({most_tokens.token_count} tokens)")
    
    print("\n✅ Testing complete!")


if __name__ == "__main__":
    asyncio.run(main())
