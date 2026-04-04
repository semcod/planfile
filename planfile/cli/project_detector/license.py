"""License detection from project files."""

from __future__ import annotations

from pathlib import Path


def _detect_license(project_path: Path) -> str | None:
    """Detect license from LICENSE file."""
    license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"]

    for license_name in license_files:
        license_path = project_path / license_name
        if license_path.exists():
            try:
                content = license_path.read_text(encoding="utf-8", errors="ignore")
                # Common license detection
                if "MIT" in content[:500]:
                    return "MIT"
                elif "Apache" in content[:500]:
                    return "Apache-2.0"
                elif "GPL" in content[:500] or "GNU GENERAL PUBLIC LICENSE" in content[:500]:
                    return "GPL"
                elif "BSD" in content[:500]:
                    return "BSD"
                else:
                    return "Unknown"
            except Exception:
                return None
    return None
