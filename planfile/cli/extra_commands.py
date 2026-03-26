"""
Additional CLI commands for planfile.
Provides export, compare, merge, template, and stats functionality.
"""

import json
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..loaders.yaml_loader import load_strategy_yaml, save_strategy_yaml
from ..models_v2 import Strategy

console = Console()


def export_to_csv(strategy: Strategy, file_path: str) -> None:
    """Export strategy to CSV format."""
    import csv
    
    with open(file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        
        # Write header
        writer.writerow(['Type', 'ID', 'Name', 'Description', 'Priority', 'Status'])
        
        # Write sprints
        for sprint in strategy.sprints:
            writer.writerow(['Sprint', sprint.id, sprint.name, 
                           f"Duration: {getattr(sprint, 'duration', 'N/A')}", 
                           '', ''])
        
        # Write tasks
        if hasattr(strategy, 'tasks') and strategy.tasks:
            for category, tasks in strategy.tasks.items():
                for task in tasks:
                    writer.writerow(['Task', task.get('id', ''), task.get('name', ''),
                                   task.get('description', ''), 
                                   task.get('priority', ''), ''])


def export_to_html(strategy: Strategy, file_path: str) -> None:
    """Export strategy to HTML format."""
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>{strategy.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #333; }}
        h2 {{ color: #666; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .sprint {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
        .task {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 3px; }}
    </style>
</head>
<body>
    <h1>{strategy.name}</h1>
    <p><strong>Goal:</strong> {strategy.goal}</p>
    <p><strong>Project Type:</strong> {strategy.project_type}</p>
    
    <h2>Sprints</h2>
"""
    
    for sprint in strategy.sprints:
        html += f"""
    <div class="sprint">
        <h3>{sprint.name}</h3>
        <p><strong>Duration:</strong> {getattr(sprint, 'duration', 'N/A')}</p>
        <p><strong>Objectives:</strong></p>
        <ul>
"""
        for obj in getattr(sprint, 'objectives', []):
            html += f"            <li>{obj}</li>\n"
        html += "        </ul>\n    </div>\n"
    
    html += """
</body>
</html>
"""
    
    with open(file_path, 'w') as f:
        f.write(html)


def compare_strategies(s1: Strategy, s2: Strategy) -> Dict[str, Any]:
    """Compare two strategies and return differences."""
    comparison = {
        'common_elements': [],
        'differences': [],
        'only_in_s1': [],
        'only_in_s2': [],
        'similarity_score': 0.0
    }
    
    # Compare goals
    goals1 = set(getattr(s1, 'goals', []))
    goals2 = set(getattr(s2, 'goals', []))
    
    comparison['common_elements'].extend(list(goals1 & goals2))
    comparison['differences'].extend([
        {'goal': g, 'in': 's1'} for g in goals1 - goals2
    ])
    comparison['differences'].extend([
        {'goal': g, 'in': 's2'} for g in goals2 - goals1
    ])
    
    # Compare sprints
    sprints1 = {s.id: s for s in s1.sprints}
    sprints2 = {s.id: s for s in s2.sprints}
    
    common_sprints = set(sprints1.keys()) & set(sprints2.keys())
    comparison['only_in_s1'].extend([s.id for s in sprints1.values() if s.id not in sprints2])
    comparison['only_in_s2'].extend([s.id for s in sprints2.values() if s.id not in sprints1])
    
    # Calculate similarity score
    total_elements = len(goals1) + len(goals2) + len(sprints1) + len(sprints2)
    common_elements = len(goals1 & goals2) + len(common_sprints)
    comparison['similarity_score'] = (2 * common_elements) / total_elements if total_elements > 0 else 0
    
    return comparison


def generate_template(project_type: str, domain: str) -> Strategy:
    """Generate a strategy template based on project type and domain."""
    templates = {
        'web': {
            'name': f'Web Application Strategy',
            'project_type': 'web',
            'domain': domain,
            'goal': f'Build a scalable web application for {domain}',
            'sprints': [
                {
                    'id': 1,
                    'name': 'Foundation & Setup',
                    'duration': '2 weeks',
                    'objectives': [
                        'Set up project structure',
                        'Configure CI/CD pipeline',
                        'Implement authentication'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Core Features',
                    'duration': '3 weeks',
                    'objectives': [
                        'Build main functionality',
                        'Implement user interface',
                        'Add database layer'
                    ]
                },
                {
                    'id': 3,
                    'name': 'Polish & Deploy',
                    'duration': '2 weeks',
                    'objectives': [
                        'Performance optimization',
                        'Security hardening',
                        'Production deployment'
                    ]
                }
            ]
        },
        'mobile': {
            'name': f'Mobile Application Strategy',
            'project_type': 'mobile',
            'domain': domain,
            'goal': f'Build a native mobile app for {domain}',
            'sprints': [
                {
                    'id': 1,
                    'name': 'UI/UX Design',
                    'duration': '2 weeks',
                    'objectives': [
                        'Design wireframes',
                        'Create mockups',
                        'Define user flow'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Core Development',
                    'duration': '4 weeks',
                    'objectives': [
                        'Implement navigation',
                        'Build key features',
                        'Integrate APIs'
                    ]
                },
                {
                    'id': 3,
                    'name': 'Testing & Release',
                    'duration': '2 weeks',
                    'objectives': [
                        'Unit and integration tests',
                        'UI testing',
                        'App store submission'
                    ]
                }
            ]
        },
        'ml': {
            'name': f'ML Pipeline Strategy',
            'project_type': 'ml',
            'domain': domain,
            'goal': f'Build machine learning pipeline for {domain}',
            'sprints': [
                {
                    'id': 1,
                    'name': 'Data Collection & Prep',
                    'duration': '2 weeks',
                    'objectives': [
                        'Collect datasets',
                        'Clean and preprocess data',
                        'Set up data pipeline'
                    ]
                },
                {
                    'id': 2,
                    'name': 'Model Development',
                    'duration': '3 weeks',
                    'objectives': [
                        'Feature engineering',
                        'Model selection and training',
                        'Validation and tuning'
                    ]
                },
                {
                    'id': 3,
                    'name': 'Deployment & Monitoring',
                    'duration': '2 weeks',
                    'objectives': [
                        'Model deployment',
                        'Performance monitoring',
                        'A/B testing setup'
                    ]
                }
            ]
        }
    }
    
    template = templates.get(project_type, templates['web'])
    
    # Create Strategy object
    strategy_data = {
        'name': template['name'],
        'project_type': template['project_type'],
        'domain': template['domain'],
        'goal': template['goal'],
        'sprints': template['sprints'],
        'quality_gates': [
            {
                'name': 'Code Quality',
                'description': 'Maintain high code quality',
                'criteria': ['Coverage > 80%', 'No critical issues'],
                'required': True
            }
        ],
        'tasks': {
            'patterns': []
        }
    }
    
    return Strategy(**strategy_data)


def calculate_strategy_stats(strategy: Strategy) -> Dict[str, Any]:
    """Calculate statistics for a strategy."""
    stats = {
        'total_sprints': len(strategy.sprints),
        'total_duration': 0,
        'total_objectives': 0,
        'avg_sprint_duration': 0,
        'quality_gates': len(getattr(strategy, 'quality_gates', [])),
        'goals': len(getattr(strategy, 'goals', []))
    }
    
    # Calculate sprint statistics
    durations = []
    for sprint in strategy.sprints:
        duration_str = getattr(sprint, 'duration', None) or '2 weeks'
        if isinstance(duration_str, str) and 'week' in duration_str:
            weeks = int(duration_str.split()[0])
            stats['total_duration'] += weeks
            durations.append(weeks)
        
        objectives = sprint.objectives if hasattr(sprint, 'objectives') else []
        stats['total_objectives'] += len(objectives)
    
    if durations:
        stats['avg_sprint_duration'] = sum(durations) / len(durations)
    
    return stats


def add_extra_commands(app):
    """Add extra commands to the CLI app."""
    
    @app.command("export")
    def export_cmd(
        strategy_file: str = typer.Argument(..., help="Strategy file to export"),
        output: str = typer.Option(..., help="Output file path"),
        format: str = typer.Option("markdown", help="Export format: yaml, json, csv, html, markdown"),
    ):
        """Export strategy to various formats."""
        try:
            strategy = load_strategy_yaml(strategy_file)
            
            if format == "yaml":
                save_strategy_yaml(strategy, output)
            elif format == "json":
                with open(output, 'w') as f:
                    json.dump(strategy.model_dump(), f, indent=2, default=str)
            elif format == "csv":
                export_to_csv(strategy, output)
            elif format == "html":
                export_to_html(strategy, output)
            elif format == "markdown":
                from ..loaders.cli_loader import export_results_to_markdown
                results = {'strategy': strategy.model_dump()}
                export_results_to_markdown(results, output)
            else:
                console.print(f"[red]Unsupported format: {format}[/red]")
                raise typer.Exit(1)
            
            console.print(f"[green]✓[/green] Exported to {output}")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Export failed: {e}")
            raise typer.Exit(1)
    
    @app.command("compare")
    def compare_cmd(
        strategy1: str = typer.Argument(..., help="First strategy file"),
        strategy2: str = typer.Argument(..., help="Second strategy file"),
        output: Optional[str] = typer.Option(None, help="Save comparison to file"),
    ):
        """Compare two strategies."""
        try:
            s1 = load_strategy_yaml(strategy1)
            s2 = load_strategy_yaml(strategy2)
            
            comparison = compare_strategies(s1, s2)
            
            # Display comparison
            console.print(Panel(f"[bold]Strategy Comparison[/bold]\nSimilarity: {comparison['similarity_score']:.2%}"))
            
            # Common elements
            if comparison['common_elements']:
                console.print("\n[green]Common Elements:[/green]")
                for item in comparison['common_elements']:
                    console.print(f"  • {item}")
            
            # Differences
            if comparison['differences']:
                console.print("\n[yellow]Differences:[/yellow]")
                for diff in comparison['differences']:
                    console.print(f"  • {diff}")
            
            # Unique to each
            if comparison['only_in_s1']:
                console.print(f"\n[blue]Only in {strategy1}:[/blue]")
                for item in comparison['only_in_s1']:
                    console.print(f"  • {item}")
            
            if comparison['only_in_s2']:
                console.print(f"\n[blue]Only in {strategy2}:[/blue]")
                for item in comparison['only_in_s2']:
                    console.print(f"  • {item}")
            
            # Save if requested
            if output:
                with open(output, 'w') as f:
                    json.dump(comparison, f, indent=2, default=str)
                console.print(f"\n[green]✓[/green] Comparison saved to {output}")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Comparison failed: {e}")
            raise typer.Exit(1)
    
    @app.command("template")
    def template_cmd(
        project_type: str = typer.Argument(..., help="Project type: web, mobile, ml"),
        domain: str = typer.Argument(..., help="Project domain"),
        output: str = typer.Option("template.yaml", help="Output file"),
    ):
        """Generate a strategy template."""
        try:
            strategy = generate_template(project_type, domain)
            save_strategy_yaml(strategy, output)
            
            console.print(f"[green]✓[/green] Template generated: {output}")
            console.print(f"  Project type: {project_type}")
            console.print(f"  Domain: {domain}")
            console.print(f"  Sprints: {len(strategy.sprints)}")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Template generation failed: {e}")
            raise typer.Exit(1)
    
    @app.command("stats")
    def stats_cmd(
        strategy_file: str = typer.Argument(..., help="Strategy file to analyze"),
    ):
        """Show strategy statistics."""
        try:
            strategy = load_strategy_yaml(strategy_file)
            stats = calculate_strategy_stats(strategy)
            
            # Create table
            table = Table(title=f"Statistics for {strategy.name}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            
            table.add_row("Total Sprints", str(stats['total_sprints']))
            table.add_row("Total Duration", f"{stats['total_duration']} weeks")
            table.add_row("Avg Sprint Duration", f"{stats['avg_sprint_duration']:.1f} weeks")
            table.add_row("Total Objectives", str(stats['total_objectives']))
            table.add_row("Quality Gates", str(stats['quality_gates']))
            table.add_row("Goals", str(stats['goals']))
            
            console.print(table)
            
            # Sprint breakdown
            console.print("\n[bold]Sprint Breakdown:[/bold]")
            for sprint in strategy.sprints:
                duration = getattr(sprint, 'duration', None) or 'N/A'
                objectives = sprint.objectives if hasattr(sprint, 'objectives') else []
                console.print(f"  • {sprint.name}: {duration}, {len(objectives)} objectives")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Stats calculation failed: {e}")
            raise typer.Exit(1)
    
    @app.command("health")
    def health_cmd(
        project_path: str = typer.Argument(".", help="Project path to check"),
    ):
        """Check project health and suggest improvements."""
        try:
            from ..analysis.generator import generator
            
            console.print("[bold]Analyzing project health...[/bold]")
            
            # Quick analysis
            strategy = generator.generate_from_current_project(
                project_path=project_path,
                max_sprints=2
            )
            
            # Show health metrics
            summary = strategy.get('summary', {})
            
            console.print("\n[bold]Health Metrics:[/bold]")
            
            # Issues
            total_issues = summary.get('total_issues', 0)
            if total_issues == 0:
                console.print("  [green]✓ No issues found[/green]")
            else:
                console.print(f"  [yellow]⚠ {total_issues} issues found[/yellow]")
            
            # Priority breakdown
            priority_breakdown = summary.get('priority_breakdown', {})
            if priority_breakdown.get('critical', 0) > 0:
                console.print(f"  [red]✗ {priority_breakdown['critical']} critical issues[/red]")
            
            # Recommendations
            console.print("\n[bold]Recommendations:[/bold]")
            
            if priority_breakdown.get('critical', 0) > 0:
                console.print("  1. Address critical issues immediately")
            
            if total_issues > 20:
                console.print("  2. Consider breaking into multiple sprints")
            
            console.print("  3. Run: planfile generate-from-files . --focus quality")
            console.print("  4. Set up regular health checks")
            
        except Exception as e:
            console.print(f"[red]✗[/red] Health check failed: {e}")
            raise typer.Exit(1)
