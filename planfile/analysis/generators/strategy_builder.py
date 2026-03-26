from typing import Dict, List, Any, Optional

def generate_goal(summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> str:
    """Generate main goal based on analysis."""
    if focus_area:
        focus_goals = {
            'quality': 'Improve overall code quality and maintainability',
            'security': 'Enhance security posture and address vulnerabilities',
            'performance': 'Optimize performance and reduce bottlenecks',
            'testing': 'Improve test coverage and test quality',
            'documentation': 'Complete and improve project documentation'
        }
        return focus_goals.get(focus_area, 'Systematically address issues found in analysis')
    
    if summary['priority_breakdown']['critical'] > 0:
        return f"Address {summary['priority_breakdown']['critical']} critical issues and improve code quality"
    elif metrics.get('average_cc', 0) > 4:
        return "Reduce code complexity and improve maintainability"
    else:
        return "Systematically address issues found in code analysis"

def generate_goals(summary: Dict[str, Any], metrics: Dict[str, Any], focus_area: Optional[str]) -> List[str]:
    """Generate goals based on analysis."""
    goals = []
    
    if summary['priority_breakdown']['critical'] > 0:
        goals.append(f"Fix all {summary['priority_breakdown']['critical']} critical issues")
    
    if metrics.get('average_cc', 0) > 3.5:
        goals.append(f"Reduce average cyclomatic complexity from {metrics['average_cc']} to ≤ 3.5")
    
    if metrics.get('critical_functions', 0) > 0:
        goals.append(f"Eliminate all {metrics['critical_functions']} high-complexity functions")
    
    if metrics.get('validation_errors', 0) > 0:
        goals.append(f"Resolve all {metrics['validation_errors']} validation errors")
    
    if metrics.get('validation_warnings', 0) > 0:
        goals.append(f"Address {metrics['validation_warnings']} validation warnings")
    
    if metrics.get('duplication_groups', 0) > 0:
        goals.append(f"Remove {metrics['duplication_groups']} code duplication groups")
    
    if metrics.get('test_coverage'):
        current = metrics['test_coverage']
        if current < 80:
            goals.append(f"Increase test coverage from {current}% to 80%")
    
    if focus_area == 'security':
        goals.append("Implement security best practices")
        goals.append("Address all security vulnerabilities")
    elif focus_area == 'performance':
        goals.append("Optimize critical performance paths")
        goals.append("Reduce resource consumption")
    elif focus_area == 'testing':
        goals.append("Achieve 80% test coverage")
        goals.append("Add integration tests")
    elif focus_area == 'documentation':
        goals.append("Document all APIs and modules")
        goals.append("Create user guides")
    
    goals.append("Improve overall code quality")
    goals.append("Ensure all files pass validation")
    
    return goals

def generate_quality_gates(metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generate quality gates based on current metrics."""
    gates = []
    
    if 'average_cc' in metrics:
        gates.append({
            'name': 'Average Cyclomatic Complexity',
            'description': 'Keep average CC below 3.5 for maintainability',
            'criteria': [f"CC̄ ≤ 3.5"],
            'required': True
        })
    
    gates.append({
        'name': 'Critical Functions',
        'description': 'No functions should have CC > 15',
        'criteria': ['All functions CC ≤ 15'],
        'required': True
    })
    
    gates.append({
        'name': 'Validation Errors',
        'description': 'All files must pass validation',
        'criteria': ['Zero validation errors'],
        'required': True
    })
    
    gates.append({
        'name': 'Validation Warnings',
        'description': 'Address all validation warnings',
        'criteria': ['Zero validation warnings'],
        'required': True
    })
    
    if 'duplication_groups' in metrics:
        gates.append({
            'name': 'Code Duplication',
            'description': 'Eliminate code duplication',
            'criteria': ['Zero duplication groups'],
            'required': True
        })
    
    gates.append({
        'name': 'Test Coverage',
        'description': 'Maintain adequate test coverage',
        'criteria': ['Coverage ≥ 80%'],
        'required': True
    })
    
    return gates

def generate_tasks(analysis_result: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Generate task breakdowns."""
    tasks = {
        'critical_refactors': [],
        'standard_refactors': [],
        'bug_fixes': [],
        'test_writing': [],
        'documentation': []
    }
    
    for issue in analysis_result['issues']:
        task = {
            'name': issue.title,
            'description': issue.description,
            'file_path': issue.file_path,
            'line_number': issue.line_number,
            'estimated_hours': parse_effort(issue.effort_estimate)
        }
        
        if issue.category == 'refactor':
            if issue.priority in ['critical', 'high']:
                tasks['critical_refactors'].append(task)
            else:
                tasks['standard_refactors'].append(task)
        elif issue.category == 'bug':
            tasks['bug_fixes'].append(task)
        elif issue.category == 'test':
            tasks['test_writing'].append(task)
        elif issue.category == 'documentation':
            tasks['documentation'].append(task)
    
    return tasks

def parse_effort(effort: Optional[str]) -> int:
    """Parse effort estimate to hours."""
    if not effort:
        return 4
    
    if 'h' in effort:
        return int(effort.replace('h', ''))
    elif 'd' in effort:
        return int(effort.replace('d', '')) * 8
    
    return 4

def generate_target_metrics(current: Dict[str, Any]) -> Dict[str, Any]:
    """Generate target metrics."""
    target = current.copy()
    
    target['average_cc'] = min(target.get('average_cc', 4), 3.5)
    target['critical_functions'] = 0
    target['validation_errors'] = 0
    target['validation_warnings'] = 0
    target['duplication_groups'] = 0
    target['test_coverage'] = max(target.get('test_coverage', 0), 80)
    
    return target

def generate_risks(analysis_result: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate risk assessment."""
    risks = []
    
    critical_count = len([i for i in analysis_result['issues'] if i.priority == 'critical'])
    
    if critical_count > 10:
        risks.append({
            'description': f"High number of critical issues ({critical_count}) may impact delivery",
            'mitigation': "Prioritize critical issues and consider additional resources"
        })
    
    if len(analysis_result['analyzed_files']) > 100:
        risks.append({
            'description': "Large codebase may require extended timeline",
            'mitigation': "Focus on high-impact files first"
        })
    
    risks.append({
        'description': "Refactoring may introduce new bugs",
        'mitigation': "Comprehensive testing and code review"
    })
    
    return risks

def generate_success_criteria(metrics: Dict[str, Any]) -> List[str]:
    """Generate success criteria."""
    criteria = []
    
    criteria.append("All quality gates pass")
    criteria.append("All generated tickets are completed")
    
    if 'average_cc' in metrics:
        criteria.append(f"Average CC reduced from {metrics['average_cc']} to ≤ 3.5")
    
    criteria.append("Zero validation errors")
    criteria.append("Code duplication eliminated")
    
    if 'test_coverage' in metrics:
        criteria.append(f"Test coverage increased to 80%")
    
    criteria.append("All files pass linting and validation")
    
    return criteria
