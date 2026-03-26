#!/usr/bin/env python3
"""
Direct integration of LiteLLM with planfile strategy generation.
"""

import os
import sys
import asyncio
from pathlib import Path
import yaml
from typing import Dict, Any, List, Optional
import json

# Add planfile to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from planfile.llm.client import call_llm
from planfile.llm.generator import generate_strategy
from planfile.models import Strategy


class LiteLLMStrategyTester:
    """Test strategies with different LiteLLM models."""
    
    def __init__(self):
        self.models_to_test = [
            # OpenAI models
            "gpt-4-turbo-preview",
            "gpt-3.5-turbo",
            # Anthropic models (via OpenRouter/Anthropic API)
            "anthropic/claude-3-opus-20240229",
            "anthropic/claude-3-sonnet-20240229",
            "anthropic/claude-3-haiku-20240307",
            # Google models
            "gemini-pro",
            # Open source models
            "replicate/llama-2-70b-chat:02e509c789964a7ea8736978a4382599e9a051f75f23364203f8973a8ee5e718",
            "togethercomputer/llama-2-70b-chat"
        ]
        
        self.test_prompts = [
            {
                "name": "Microservices Migration",
                "focus": "architecture",
                "sprints": 4,
                "description": "Migrate monolithic application to microservices"
            },
            {
                "name": "AI Platform Development",
                "focus": "ml-engineering",
                "sprints": 3,
                "description": "Build an AI/ML platform with model training and deployment"
            },
            {
                "name": "Security Compliance",
                "focus": "security",
                "sprints": 5,
                "description": "Achieve SOC 2 Type II compliance"
            },
            {
                "name": "Performance Optimization",
                "focus": "performance",
                "sprints": 2,
                "description": "Optimize application performance and scalability"
            }
        ]
    
    def create_test_prompt(self, prompt_config: Dict[str, Any]) -> str:
        """Create a test prompt from configuration."""
        return f"""
        Generate a comprehensive software development strategy for: {prompt_config['name']}
        
        Project Description:
        {prompt_config['description']}
        
        Focus Area: {prompt_config['focus']}
        Number of Sprints: {prompt_config['sprints']}
        
        Requirements:
        1. Create a YAML strategy with proper structure
        2. Include detailed sprint objectives
        3. Define quality gates with metrics
        4. Add task patterns with priorities
        5. Include resource estimates
        
        Output only valid YAML wrapped in ```yaml``` blocks.
        """
    
    async def test_model_with_prompt(
        self, 
        model: str, 
        prompt: str
    ) -> Dict[str, Any]:
        """Test a specific model with a prompt."""
        try:
            import time
            start_time = time.time()
            
            response = call_llm(prompt, model=model, temperature=0.3)
            
            end_time = time.time()
            
            # Extract YAML from response
            yaml_content = None
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
            elif "```" in response:
                yaml_content = response.split("```")[1].split("```")[0]
            
            # Validate YAML if present
            is_valid_yaml = False
            strategy_obj = None
            if yaml_content:
                try:
                    data = yaml.safe_load(yaml_content)
                    is_valid_yaml = True
                    
                    # Try to validate with Strategy model
                    try:
                        strategy_obj = Strategy(**data)
                    except Exception as e:
                        pass
                        
                except yaml.YAMLError:
                    pass
            
            return {
                "model": model,
                "success": True,
                "response_time": end_time - start_time,
                "response_length": len(response),
                "has_yaml": yaml_content is not None,
                "is_valid_yaml": is_valid_yaml,
                "is_valid_strategy": strategy_obj is not None,
                "response_preview": response[:200] + "..." if len(response) > 200 else response,
                "yaml_preview": yaml_content[:200] + "..." if yaml_content and len(yaml_content) > 200 else yaml_content
            }
            
        except Exception as e:
            return {
                "model": model,
                "success": False,
                "error": str(e),
                "response_time": 0,
                "response_length": 0,
                "has_yaml": False,
                "is_valid_yaml": False,
                "is_valid_strategy": False
            }
    
    async def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive tests across models and prompts."""
        print("=" * 60)
        print("LITELLM COMPREHENSIVE STRATEGY TESTS")
        print("=" * 60)
        
        # Check API keys
        api_keys = {
            'OPENAI_API_KEY': os.environ.get('OPENAI_API_KEY'),
            'ANTHROPIC_API_KEY': os.environ.get('ANTHROPIC_API_KEY'),
            'OPENROUTER_API_KEY': os.environ.get('OPENROUTER_API_KEY'),
            'GOOGLE_API_KEY': os.environ.get('GOOGLE_API_KEY'),
            'REPLICATE_API_TOKEN': os.environ.get('REPLICATE_API_TOKEN'),
            'TOGETHER_AI_API_KEY': os.environ.get('TOGETHER_AI_API_KEY')
        }
        
        print("\n🔑 API Key Status:")
        for key, value in api_keys.items():
            status = "✅" if value else "❌"
            print(f"  {key}: {status}")
        
        print("\n🧪 Testing models...")
        
        results = {}
        
        for prompt_config in self.test_prompts:
            print(f"\n📝 Prompt: {prompt_config['name']}")
            print("-" * 40)
            
            prompt = self.create_test_prompt(prompt_config)
            prompt_results = []
            
            for model in self.models_to_test:
                print(f"  🔄 Testing {model}...")
                
                result = await self.test_model_with_prompt(model, prompt)
                prompt_results.append(result)
                
                status = "✅" if result['success'] else "❌"
                yaml_status = "📄" if result['has_yaml'] else "📝"
                valid_status = "✨" if result['is_valid_strategy'] else "⚠️"
                
                print(f"    {status} {yaml_status} {valid_status} {result['response_time']:.2f}s")
                
                if not result['success']:
                    print(f"      Error: {result.get('error', 'Unknown error')}")
            
            results[prompt_config['name']] = prompt_results
        
        # Generate summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        
        summary = self.generate_summary(results)
        print(summary)
        
        # Save detailed results
        output_file = Path("litellm-test-results.json")
        with open(output_file, 'w') as f:
            json.dump({
                'timestamp': str(asyncio.get_event_loop().time()),
                'api_keys_present': {k: bool(v) for k, v in api_keys.items()},
                'results': results,
                'summary': summary
            }, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
        return results
    
    def generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate a summary of test results."""
        summary_lines = []
        
        # Overall stats
        all_results = []
        for prompt_results in results.values():
            all_results.extend(prompt_results)
        
        total = len(all_results)
        successful = sum(1 for r in all_results if r['success'])
        with_yaml = sum(1 for r in all_results if r['has_yaml'])
        with_valid_strategy = sum(1 for r in all_results if r['is_valid_strategy'])
        
        summary_lines.append(f"Total tests: {total}")
        summary_lines.append(f"Successful API calls: {successful} ({successful/total*100:.1f}%)")
        summary_lines.append(f"Generated YAML: {with_yaml} ({with_yaml/total*100:.1f}%)")
        summary_lines.append(f"Valid strategies: {with_valid_strategy} ({with_valid_strategy/total*100:.1f}%)")
        
        # Best performers
        successful_results = [r for r in all_results if r['success']]
        if successful_results:
            fastest = min(successful_results, key=lambda x: x['response_time'])
            summary_lines.append(f"\nFastest model: {fastest['model']} ({fastest['response_time']:.2f}s)")
            
            valid_strategies = [r for r in successful_results if r['is_valid_strategy']]
            if valid_strategies:
                best_strategy = max(valid_strategies, key=lambda x: x['response_length'])
                summary_lines.append(f"Most detailed: {best_strategy['model']} ({best_strategy['response_length']} chars)")
        
        # Model performance table
        summary_lines.append("\nModel Performance:")
        summary_lines.append("-" * 40)
        
        model_stats = {}
        for r in all_results:
            model = r['model']
            if model not in model_stats:
                model_stats[model] = {'total': 0, 'success': 0, 'valid': 0}
            model_stats[model]['total'] += 1
            if r['success']:
                model_stats[model]['success'] += 1
            if r['is_valid_strategy']:
                model_stats[model]['valid'] += 1
        
        for model, stats in sorted(model_stats.items()):
            success_rate = stats['success'] / stats['total'] * 100
            valid_rate = stats['valid'] / stats['total'] * 100
            summary_lines.append(
                f"  {model}: {stats['success']}/{stats['total']} ({success_rate:.0f}%) "
                f"valid: {stats['valid']} ({valid_rate:.0f}%)"
            )
        
        return "\n".join(summary_lines)


async def test_specific_strategy():
    """Test generating a specific strategy with different models."""
    print("\n" + "=" * 60)
    print("SPECIFIC STRATEGY GENERATION TEST")
    print("=" * 60)
    
    # Test with the microservices migration strategy
    strategy_path = Path(__file__).parent / "strategies" / "microservices-migration.yaml"
    
    if not strategy_path.exists():
        print(f"❌ Strategy file not found: {strategy_path}")
        return
    
    # Read the strategy as a reference
    with open(strategy_path, 'r') as f:
        reference_strategy = f.read()
    
    # Create a new prompt based on it
    prompt = f"""
    Based on this microservices migration strategy, create a new strategy for "Mobile App Development".
    Keep the same structure and quality, but adapt for a mobile application project.
    
    Reference strategy structure:
    {reference_strategy[:1000]}...
    
    Generate a complete YAML strategy for:
    - Project: Food Delivery Mobile App
    - Platform: iOS & Android (React Native)
    - Focus: User experience, performance, and scalability
    - Sprints: 4
    """
    
    models_to_try = [
        "gpt-3.5-turbo",
        "anthropic/claude-3-haiku-20240307"
    ]
    
    if os.environ.get('OPENROUTER_API_KEY'):
        models_to_try.append("anthropic/claude-3-haiku")
    
    for model in models_to_try:
        print(f"\n🔄 Generating with {model}...")
        
        try:
            response = call_llm(prompt, model=model, temperature=0.3)
            
            # Save the response
            output_file = Path(f"generated-strategy-{model.replace('/', '-')}.yaml")
            
            # Extract YAML
            if "```yaml" in response:
                yaml_content = response.split("```yaml")[1].split("```")[0]
                with open(output_file, 'w') as f:
                    f.write(yaml_content)
                print(f"✅ Strategy saved to: {output_file}")
            else:
                print(f"⚠️  No YAML found in response")
                with open(output_file.with_suffix('.txt'), 'w') as f:
                    f.write(response)
                print(f"📝 Response saved to: {output_file.with_suffix('.txt')}")
                
        except Exception as e:
            print(f"❌ Error: {e}")


async def main():
    """Main test function."""
    # Run comprehensive tests
    tester = LiteLLMStrategyTester()
    await tester.run_comprehensive_test()
    
    # Test specific strategy generation
    await test_specific_strategy()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
