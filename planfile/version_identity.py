"""Single runtime version and autonomy schema identity helpers for Planfile."""

from __future__ import annotations

import importlib.metadata
import os
import re
import sys
from pathlib import Path

RUNTIME_VERSION_CONSTANT = "0.1.127"

SUPPORTED_AUTONOMY_SCHEMAS: dict[str, str] = {
    "ticket": "planfile.ticket/v1",
    "ticket_create": "planfile.ticket-create/v1",
    "ticket_update": "planfile.ticket-update/v1",
    "comparative_finding": "planfile.comparative-finding/v1",
    "comparative_findings_admit_request": "planfile.comparative-findings-admit-request/v1",
    "compiled_work_plan": "subactor.compiled-work-plan/v1",
    "compiled_work_plan_v2": "subactor.compiled-work-plan/v2",
    "delivery_placement_v2": "planfile.delivery-placement/v2",
    "ticket_candidate_v2": "subactor.ticket-candidate/v2",
    "delivery_plan_bundle": "planfile.delivery-plan-bundle/v1",
    "trusted_delivery_targets": "planfile.trusted-delivery-targets/v1",
    "external_import_metadata": "autodo.planfile-import/v1",
    "legacy_strategy_compatibility": "planfile.strategy.legacy-yaml/v2",
}

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _matched_distribution_version(pkg_dir: Path) -> str | None:
    resolved_pkg_dir = pkg_dir.resolve()
    try:
        distributions = list(importlib.metadata.distributions())
    except Exception:
        return None
    for dist in distributions:
        name = str(dist.metadata.get("Name", "") or "").strip().lower().replace("_", "-")
        if name != "planfile":
            continue
        try:
            located = Path(dist.locate_file("planfile")).resolve()
        except Exception:
            continue
        if located == resolved_pkg_dir:
            version = str(getattr(dist, "version", "") or "").strip()
            if version:
                return version
    return None


def _read_pyproject_version(checkout_root: Path) -> str | None:
    pyproject_path = checkout_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return None
    try:
        try:
            import tomllib
        except ModuleNotFoundError:  # Python 3.10 uses the locked tomli dependency.
            import tomli as tomllib
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        version = data.get("project", {}).get("version")
        return str(version).strip() if version else None
    except Exception:
        return None


def resolve_runtime_version(
    declared_constant: str = RUNTIME_VERSION_CONSTANT,
    *,
    package_file: str | Path | None = None,
) -> str:
    """Resolve Planfile's runtime version from checkout constant or matched wheel metadata.

    Checkout source trees bind directly to ``declared_constant`` instead of global
    environment metadata so a shared CI/executor interpreter carrying an older
    ``.dist-info`` never shadows checked-out code.  Installed wheels without a
    parent ``pyproject.toml`` resolve against the matched distribution metadata
    co-located with ``package_file``.
    """
    pkg_dir = Path(package_file or __file__).resolve().parent
    checkout_root = pkg_dir.parent
    if (checkout_root / "pyproject.toml").is_file():
        return str(declared_constant)
    matched = _matched_distribution_version(pkg_dir)
    if matched is not None:
        return matched
    return str(declared_constant)


def resolve_source_sha(root: Path | None = None) -> str | None:
    """Return the build/source commit SHA if explicitly configured or readable from git."""
    for env_key in ("PLANFILE_BUILD_SHA", "PLANFILE_SOURCE_SHA"):
        raw = str(os.environ.get(env_key, "") or "").strip()
        if raw and _SHA_RE.fullmatch(raw):
            return raw.lower()
    if root is None:
        return None
    resolved_root = Path(root).resolve()
    if not (resolved_root / ".git").exists():
        return None
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(resolved_root),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    candidate = proc.stdout.strip()
    if proc.returncode == 0 and _SHA_RE.fullmatch(candidate):
        return candidate.lower()
    return None


def get_runtime_identity(
    *,
    package_file: str | Path | None = None,
    runtime_version: str | None = None,
) -> dict[str, object]:
    """Return bounded runtime version, source SHA, install mode, and autonomy schemas."""
    if package_file is None:
        loaded_pkg = sys.modules.get("planfile")
        pkg_file_attr = getattr(loaded_pkg, "__file__", None) if loaded_pkg is not None else None
        pkg_dir = Path(pkg_file_attr or __file__).resolve().parent
    else:
        pkg_dir = Path(package_file).resolve().parent
    checkout_root = pkg_dir.parent
    install_mode = "checkout" if (checkout_root / "pyproject.toml").is_file() else "distribution"
    actual_version = runtime_version
    if actual_version is None:
        loaded_pkg = sys.modules.get("planfile")
        if loaded_pkg is not None and isinstance(getattr(loaded_pkg, "__version__", None), str):
            actual_version = loaded_pkg.__version__
        else:
            actual_version = resolve_runtime_version(package_file=pkg_dir / "__init__.py")
    return {
        "package": "planfile",
        "version": str(actual_version),
        "install_mode": install_mode,
        "source_sha": resolve_source_sha(checkout_root if install_mode == "checkout" else None),
        "distribution_version": _matched_distribution_version(pkg_dir),
        "pyproject_version": (
            _read_pyproject_version(checkout_root) if install_mode == "checkout" else None
        ),
        "version_identifies_active_deployment": False,
        "schema_versions": dict(SUPPORTED_AUTONOMY_SCHEMAS),
    }


__all__ = [
    "RUNTIME_VERSION_CONSTANT",
    "SUPPORTED_AUTONOMY_SCHEMAS",
    "get_runtime_identity",
    "resolve_runtime_version",
    "resolve_source_sha",
]
