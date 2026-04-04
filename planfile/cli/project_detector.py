"""Project auto-detection module for planfile init.

This is now a compatibility shim - the actual implementation is in planfile.cli.project_detector package.
"""

# Re-export everything from the new package for backward compatibility
from planfile.cli.project_detector import (  # noqa: F401
    DetectedProject,
    DetectedQualityGate,
    detect_project,
    get_detected_values,
)

__all__ = [
    "DetectedProject",
    "DetectedQualityGate",
    "detect_project",
    "get_detected_values",
]
