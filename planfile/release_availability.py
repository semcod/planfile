#!/usr/bin/env python3
"""Check that Planfile source and runtime release metadata are publishable."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_NON_PORTABLE_DEP_RE = re.compile(r"@\s*(?:git\+|https?://|file:)", re.IGNORECASE)


def _load_toml(path: Path) -> dict[str, object]:
    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 uses the locked tomli dependency.
        import tomli as tomllib
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _assigned_name_constant(tree: ast.Module, target_name: str) -> tuple[bool, str | None]:
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if target_name in names:
                return True, _string_constant(stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == target_name and stmt.value is not None:
                return True, _string_constant(stmt.value)
    return False, None


def extract_runtime_version_constants(root: Path) -> dict[str, str | None]:
    """Inspect runtime version constants from package source without mutating sys.modules."""
    init_path = root / "planfile/__init__.py"
    identity_path = root / "planfile/version_identity.py"
    init_version: str | None = None
    identity_version: str | None = None
    init_uses_resolver = False

    if init_path.is_file():
        init_tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
        has_version, literal = _assigned_name_constant(init_tree, "__version__")
        if has_version and literal is not None:
            init_version = literal
        elif has_version:
            for stmt in init_tree.body:
                if (
                    isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "__version__" for t in stmt.targets)
                    and isinstance(stmt.value, ast.Call)
                    and isinstance(stmt.value.func, ast.Name)
                    and stmt.value.func.id in {"_resolve_runtime_version", "resolve_runtime_version"}
                ):
                    init_uses_resolver = True
                    if stmt.value.args:
                        init_version = _string_constant(stmt.value.args[0])

    if identity_path.is_file():
        id_tree = ast.parse(identity_path.read_text(encoding="utf-8"), filename=str(identity_path))
        _, identity_version = _assigned_name_constant(id_tree, "RUNTIME_VERSION_CONSTANT")

    effective = init_version if init_version is not None else identity_version
    return {
        "init_version": init_version,
        "identity_version": identity_version,
        "init_uses_resolver": "true" if init_uses_resolver else "false",
        "effective_version": effective,
    }


def _git_head_sha(root: Path) -> str | None:
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = proc.stdout.strip()
    if proc.returncode == 0 and _SHA_RE.fullmatch(sha):
        return sha.lower()
    return None


def qualify_distribution_install(
    root: Path,
    *,
    clean_env_result: dict[str, object] | None = None,
) -> dict[str, object]:
    """Report full dependency portability and offline clean-environment qualification."""
    project = _load_toml(root / "pyproject.toml").get("project", {})
    assert isinstance(project, dict)
    source_version = str(project["version"])
    declared_dependencies = [str(dep) for dep in (project.get("dependencies") or [])]
    non_portable = [dep for dep in declared_dependencies if _NON_PORTABLE_DEP_RE.search(dep)]
    blockers = [
        {
            "code": "non_portable_vcs_dependency",
            "dependency": dep,
            "tracking_issues": ["#303", "#329"],
        }
        for dep in non_portable
    ]
    clean_ok = bool(
        not non_portable
        and isinstance(clean_env_result, dict)
        and clean_env_result.get("ok") is True
        and clean_env_result.get("network_disabled") is True
        and clean_env_result.get("all_public_dependencies_imported") is True
    )
    if non_portable:
        status = "blocked"
    elif clean_ok:
        status = "qualified"
    elif clean_env_result is not None:
        status = "failed"
    else:
        status = "unverified"
    return {
        "schema": "planfile.distribution-qualification/v1",
        "package": str(project.get("name", "planfile")),
        "source_version": source_version,
        "source_pin": _git_head_sha(root),
        "declared_dependencies": declared_dependencies,
        "non_portable_dependencies": non_portable,
        "clean_environment_result": clean_env_result,
        "qualified_full_offline_install": clean_ok,
        "minimal_sdk_import_is_full_qualification": False,
        "status": status,
        "blockers": blockers,
    }


def version_key(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(value)
    if not match:
        raise ValueError(f"unsupported version: {value}")
    return tuple(int(part) for part in match.groups())


def published_info(url: str) -> dict[str, str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        info = json.load(response).get("info", {})
    return {"version": str(info.get("version", "")), "python_requires": str(info.get("requires_python", ""))}


def check(
    root: Path,
    *,
    offline: bool = False,
    runtime_version: str | None = None,
    clean_env_result: dict[str, object] | None = None,
) -> dict[str, object]:
    project = _load_toml(root / "pyproject.toml")
    metadata = json.loads((root / "planfile/release-metadata.json").read_text())
    source_version = str(project["project"]["version"])
    runtime = metadata["runtime"]
    declared_published = metadata["published"]
    observed = (
        {"version": str(declared_published["version"]), "python_requires": str(declared_published["python_requires"])}
        if offline
        else published_info(str(declared_published["index"]))
    )
    errors: list[str] = []
    if source_version != str(metadata["source"]["version"]):
        errors.append("source metadata does not match pyproject")
    if str(runtime["version"]) != source_version:
        errors.append("runtime version does not match source version")
    if version_key(source_version) > version_key(observed["version"]):
        errors.append(f"source version {source_version} is newer than published {observed['version']}")
    if str(project["project"].get("requires-python")) != str(runtime["python_requires"]):
        errors.append("runtime python_requires does not match pyproject")
    if str(runtime["python_requires"]) != str(observed["python_requires"]):
        errors.append("published python_requires does not match runtime metadata")

    has_init = (root / "planfile/__init__.py").is_file()
    has_identity = (root / "planfile/version_identity.py").is_file()
    extracted = extract_runtime_version_constants(root) if (has_init or has_identity) else {}
    effective_constant = extracted.get("effective_version")
    if has_init or has_identity:
        init_v = extracted.get("init_version")
        id_v = extracted.get("identity_version")
        if init_v is not None and id_v is not None and init_v != id_v:
            errors.append("package __init__ and version_identity constants diverge")
        if effective_constant is None or effective_constant != source_version:
            errors.append("runtime __version__ constant does not match pyproject")
    if runtime_version is not None and runtime_version != source_version:
        errors.append("loaded runtime __version__ does not match pyproject")

    qualification = qualify_distribution_install(root, clean_env_result=clean_env_result)
    return {
        "package": metadata["package"],
        "source_version": source_version,
        "published_version": observed["version"],
        "python_requires": observed["python_requires"],
        "runtime_version_constant": effective_constant,
        "distribution_qualification": qualification,
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        result = check(args.root, offline=args.offline)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"ok": False, "errors": [str(error)]}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
