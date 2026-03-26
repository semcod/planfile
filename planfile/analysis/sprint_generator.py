"""
Sprint generation module for planfile.
Creates sprints and tickets from extracted analysis data.
"""

from typing import Dict, List, Any
from dataclasses import asdict
from .models import ExtractedIssue


class SprintGenerator:
    """Generates sprints and tickets from extracted information."""
    
    def __init__(self):
        self.sprint_templates = {
            'critical': {
                'name': 'Critical Issues Sprint',
                'duration': '1 week',
                'focus': 'Fix critical bugs and issues'
            },
            'quality': {
                'name': 'Quality Improvement Sprint',
                'duration': '2 weeks',
                'focus': 'Improve code quality and test coverage'
            },
            'feature': {
                'name': 'Feature Development Sprint',
                'duration': '2 weeks',
                'focus': 'Implement new features'
            },
            'optimization': {
                'name': 'Performance Optimization Sprint',
                'duration': '1 week',
                'focus': 'Optimize performance and reduce complexity'
            }
        }
    
    def generate_sprints(self, analysis_result: Dict[str, Any], max_sprints: int = 4) -> List[Dict[str, Any]]:
        """Generate sprints based on analysis results."""
        issues = analysis_result['issues']
        metrics = analysis_result['metrics']
        
        # Group issues by priority
        issue_groups = self._group_issues_by_priority(issues)
        
        sprint_creators = [
            ("Critical Issues Resolution", "1 week", ["Fix all critical bugs and errors"], 
             lambda: issue_groups['critical'][:10]),
            ("Quality & High Priority", "2 weeks", ["Address high priority issues", "Improve code quality"], 
             lambda: self._get_high_and_quality_issues(issue_groups)),
            ("Feature Development", "2 weeks", ["Implement features and improvements"], 
             lambda: self._get_remaining_medium_issues(issue_groups)),
            ("Polish & Documentation", "1 week", ["Documentation", "Minor improvements"], 
             lambda: issue_groups['low'][:10]),
        ]
        
        sprints = []
        for i, (name, duration, objectives, issues_getter) in enumerate(sprint_creators[:max_sprints]):
            issues_for_sprint = issues_getter()
            if issues_for_sprint:
                sprint = self._create_sprint(
                    f"sprint-{i+1}",
                    name,
                    duration,
                    objectives,
                    issues_for_sprint
                )
                sprints.append(sprint)
        
        return sprints
    
    def _group_issues_by_priority(self, issues: List[ExtractedIssue]) -> Dict[str, List[ExtractedIssue]]:
        """Group issues by priority."""
        return {
            'critical': [i for i in issues if i.priority == 'critical'],
            'high': [i for i in issues if i.priority == 'high'],
            'medium': [i for i in issues if i.priority == 'medium'],
            'low': [i for i in issues if i.priority == 'low'],
        }
    
    def _get_high_and_quality_issues(self, issue_groups: Dict[str, List[ExtractedIssue]]) -> List[ExtractedIssue]:
        """Get high priority issues plus quality-related medium issues."""
        high_issues = issue_groups['high']
        quality_medium = [i for i in issue_groups['medium'] if i.category in ['refactor', 'test']]
        return (high_issues + quality_medium)[:15]
    
    def _get_remaining_medium_issues(self, issue_groups: Dict[str, List[ExtractedIssue]]) -> List[ExtractedIssue]:
        """Get medium issues that weren't included in the quality sprint."""
        high_and_quality = self._get_high_and_quality_issues(issue_groups)
        remaining = [i for i in issue_groups['medium'] if i not in high_and_quality]
        return remaining[:15]
    
    def _create_sprint(self, sprint_id: str, name: str, duration: str, objectives: List[str], issues: List[ExtractedIssue]) -> Dict[str, Any]:
        """Create a sprint from issues."""
        # Group issues by category for task patterns
        category_groups = {}
        for issue in issues:
            if issue.category not in category_groups:
                category_groups[issue.category] = []
            category_groups[issue.category].append(issue)
        
        task_patterns = []
        for category, category_issues in category_groups.items():
            task_patterns.append({
                'name': f"Resolve {category.title()} Issues",
                'description': f"Fix {len(category_issues)} {category} issues",
                'task_type': self._map_category_to_task_type(category),
                'priority': self._get_highest_priority(category_issues),
                'estimate': self._estimate_effort(category_issues),
                'issues': [asdict(issue) for issue in category_issues]
            })
        
        return {
            'id': sprint_id,
            'name': name,
            'duration': duration,
            'objectives': objectives,
            'task_patterns': task_patterns,
            'issue_count': len(issues)
        }
    
    def _map_category_to_task_type(self, category: str) -> str:
        """Map issue category to task type."""
        mapping = {
            'bug': 'bugfix',
            'refactor': 'refactor',
            'feature': 'feature',
            'test': 'test',
            'documentation': 'documentation',
            'performance': 'optimize',
            'technical_debt': 'refactor',
            'security': 'security',
            'quality': 'refactor'
        }
        return mapping.get(category, 'task')
    
    def _get_highest_priority(self, issues: List[ExtractedIssue]) -> str:
        """Get highest priority from issues."""
        priority_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
        highest = max(issues, key=lambda x: priority_order.get(x.priority, 0))
        return highest.priority
    
    def _estimate_effort(self, issues: List[ExtractedIssue]) -> str:
        """Estimate total effort for issues."""
        total_hours = 0
        for issue in issues:
            if issue.effort_estimate:
                # Parse existing estimate
                if 'h' in issue.effort_estimate:
                    total_hours += int(issue.effort_estimate.replace('h', ''))
                elif 'd' in issue.effort_estimate:
                    total_hours += int(issue.effort_estimate.replace('d', '')) * 8
            else:
                # Default estimate based on priority
                priority_hours = {'critical': 8, 'high': 6, 'medium': 4, 'low': 2}
                total_hours += priority_hours.get(issue.priority, 4)
        
        # Convert to days
        days = total_hours / 8
        if days < 1:
            return f"{total_hours}h"
        else:
            return f"{int(days)}d"
    
    def generate_tickets(self, analysis_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Generate tickets from issues."""
        issues = analysis_result['issues']
        
        tickets = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for issue in issues:
            ticket = {
                'title': issue.title,
                'description': issue.description,
                'priority': issue.priority,
                'category': issue.category,
                'file_path': issue.file_path,
                'line_number': issue.line_number,
                'effort_estimate': issue.effort_estimate,
                'tags': issue.tags
            }
            
            tickets[issue.priority].append(ticket)
        
        return tickets
