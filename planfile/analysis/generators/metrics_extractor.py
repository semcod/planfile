from typing import Dict, Any, Optional

def extract_key_metrics(analysis_result: Dict[str, Any], external_metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract key metrics from analysis."""
    metrics = {}
    
    if external_metrics:
        metrics.update(external_metrics)
    
    _extract_cc_metrics(analysis_result, metrics)
    _extract_critical_metrics(analysis_result, metrics)
    _extract_validation_metrics(analysis_result, metrics)
    _extract_duplication_metrics(analysis_result, metrics)
    _extract_coverage_metrics(analysis_result, metrics)
    
    return metrics

def _extract_cc_metrics(analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    cc_metrics = [m for m in analysis_result['metrics'] if 'CC' in m.name or 'complexity' in m.name.lower()]
    if cc_metrics:
        avg_cc = sum(m.value for m in cc_metrics if isinstance(m.value, (int, float))) / len(cc_metrics)
        metrics['average_cc'] = round(avg_cc, 1)

def _extract_critical_metrics(analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    critical_funcs = [m for m in analysis_result['metrics'] if 'critical' in m.name.lower() and 'function' in m.name.lower()]
    if critical_funcs:
        metrics['critical_functions'] = sum(m.value for m in critical_funcs if isinstance(m.value, int))

def _extract_validation_metrics(analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    errors = [m for m in analysis_result['metrics'] if 'error' in m.name.lower()]
    warnings = [m for m in analysis_result['metrics'] if 'warning' in m.name.lower()]
    metrics['validation_errors'] = sum(m.value for m in errors if isinstance(m.value, int))
    metrics['validation_warnings'] = sum(m.value for m in warnings if isinstance(m.value, int))

def _extract_duplication_metrics(analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    dup_metrics = [m for m in analysis_result['metrics'] if 'duplication' in m.name.lower()]
    if dup_metrics:
        metrics['duplication_groups'] = sum(m.value for m in dup_metrics if isinstance(m.value, int))

def _extract_coverage_metrics(analysis_result: Dict[str, Any], metrics: Dict[str, Any]) -> None:
    coverage = [m for m in analysis_result['metrics'] if 'coverage' in m.name.lower()]
    if coverage:
        metrics['test_coverage'] = coverage[0].value
