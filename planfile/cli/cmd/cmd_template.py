"""Template generation CLI command — extracted from extra_commands.py."""

import typer
from rich.console import Console

from planfile.core.models import Strategy
from planfile.loaders.yaml_loader import save_strategy_yaml

console = Console()


def generate_template(project_type: str, domain: str) -> Strategy:
    """Generate a strategy template based on project type and domain."""
    templates = {
        'web': {
            'name': 'Web Application Strategy',
            'project_type': 'web',
            'domain': domain,
            'goal': f'Build a scalable web application for {domain}',
            'sprints': [
                {'id': 1, 'name': 'Foundation & Setup', 'duration': '2 weeks',
                 'objectives': ['Set up project structure', 'Configure CI/CD pipeline', 'Implement authentication']},
                {'id': 2, 'name': 'Core Features', 'duration': '3 weeks',
                 'objectives': ['Build main functionality', 'Implement user interface', 'Add database layer']},
                {'id': 3, 'name': 'Polish & Deploy', 'duration': '2 weeks',
                 'objectives': ['Performance optimization', 'Security hardening', 'Production deployment']},
            ]
        },
        'mobile': {
            'name': 'Mobile Application Strategy',
            'project_type': 'mobile',
            'domain': domain,
            'goal': f'Build a native mobile app for {domain}',
            'sprints': [
                {'id': 1, 'name': 'UI/UX Design', 'duration': '2 weeks',
                 'objectives': ['Design wireframes', 'Create mockups', 'Define user flow']},
                {'id': 2, 'name': 'Core Development', 'duration': '4 weeks',
                 'objectives': ['Implement navigation', 'Build key features', 'Integrate APIs']},
                {'id': 3, 'name': 'Testing & Release', 'duration': '2 weeks',
                 'objectives': ['Unit and integration tests', 'UI testing', 'App store submission']},
            ]
        },
        'ml': {
            'name': 'ML Pipeline Strategy',
            'project_type': 'ml',
            'domain': domain,
            'goal': f'Build machine learning pipeline for {domain}',
            'sprints': [
                {'id': 1, 'name': 'Data Collection & Prep', 'duration': '2 weeks',
                 'objectives': ['Collect datasets', 'Clean and preprocess data', 'Set up data pipeline']},
                {'id': 2, 'name': 'Model Development', 'duration': '3 weeks',
                 'objectives': ['Feature engineering', 'Model selection and training', 'Validation and tuning']},
                {'id': 3, 'name': 'Deployment & Monitoring', 'duration': '2 weeks',
                 'objectives': ['Model deployment', 'Performance monitoring', 'A/B testing setup']},
            ]
        },
        'api': {
            'name': 'REST API Strategy',
            'project_type': 'api',
            'domain': domain,
            'goal': f'Build a simple Python REST API for {domain}',
            'sprints': [
                {'id': 1, 'name': 'Specification & Architecture', 'duration': '1 week',
                 'objectives': ['Define API endpoints and data models (OpenAPI spec)',
                                'Choose framework (FastAPI) and project dependencies',
                                'Set up project structure and virtual environment']},
                {'id': 2, 'name': 'Implementation', 'duration': '2 weeks',
                 'objectives': ['Implement CRUD endpoints', 'Add input validation with Pydantic models',
                                'Configure database / storage layer']},
                {'id': 3, 'name': 'Testing', 'duration': '1 week',
                 'objectives': ['Write unit tests with pytest', 'Write integration tests with TestClient',
                                'Achieve >80% code coverage']},
                {'id': 4, 'name': 'Deploy & Monitoring', 'duration': '1 week',
                 'objectives': ['Dockerize the application', 'Configure CI/CD pipeline',
                                'Add health-check endpoint and basic metrics']},
            ]
        }
    }

    template = templates.get(project_type, templates['web'])

    strategy_data = {
        'name': template['name'],
        'project_type': template['project_type'],
        'domain': template['domain'],
        'goal': template['goal'],
        'sprints': template['sprints'],
        'quality_gates': [
            {'name': 'Code Quality', 'description': 'Maintain high code quality',
             'criteria': ['Coverage > 80%', 'No critical issues'], 'required': True}
        ],
    }

    return Strategy(**strategy_data)


def register_template_commands(app: typer.Typer) -> None:
    """Register template command on the typer app."""

    @app.command("template")
    def template_cmd(
        project_type: str = typer.Argument(..., help="Project type: web, mobile, ml, api"),
        domain: str = typer.Argument(..., help="Project domain"),
        output: str = typer.Option("template.yaml", help="Output file"),
    ) -> None:
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
